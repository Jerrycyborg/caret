import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import aiosqlite

import database
from database import init_db
from routers.channels import ChannelMessageRequest, receive_channel_message, receive_telegram_webhook
from services.executors import executor_registry_payload
from services.orchestrator import (
    APPROVAL_SCOPE_BOUNDARY,
    APPROVAL_SCOPE_NONE,
    APPROVAL_SCOPE_TASK,
    APPROVAL_STATUS_PENDING,
    TASK_STATUS_BOUNDARY_APPROVAL_REQUIRED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_PLAN_PENDING,
    TASK_STATUS_REJECTED,
    create_task,
    get_task,
    list_tasks,
    plan_prompt,
    resolve_approval,
)
from services.support_daemon import SupportIssue, SupportSnapshot, _persist_support_issues, evaluate_support_snapshot, support_daemon_status
from unittest.mock import patch


class BackendContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self.tempdir.name) / "oxy-test.db"
        await init_db()

    async def asyncTearDown(self):
        self.tempdir.cleanup()

    async def test_task_classification_and_executor_routing(self):
        cases = [
            ("Printer cleanup and Teams lag", "device_support", "local_device", "local_device_executor", APPROVAL_SCOPE_TASK),
            ("Build the project and generate artifacts", "project_build", "openclaw", "openclaw_executor", APPROVAL_SCOPE_TASK),
            ("Run recon for the target", "security_assessment", "wraith", "wraith_executor", APPROVAL_SCOPE_TASK),
            ("Inspect repo status and debug code issue", "developer_support", "local_dev", "local_dev_executor", APPROVAL_SCOPE_NONE),
        ]
        for prompt, task_class, domain, executor, approval_scope in cases:
            with self.subTest(prompt=prompt):
                plan = plan_prompt(prompt)
                self.assertEqual(plan.task_class, task_class)
                self.assertEqual(plan.execution_domain, domain)
                self.assertEqual(plan.assigned_executor, executor)
                self.assertEqual(plan.approval_scope, approval_scope)

    async def test_read_only_task_auto_runs_to_completion(self):
        task = await create_task("Inspect repo and read README.md")
        self.assertEqual(task["task"]["status"], TASK_STATUS_COMPLETED)
        self.assertEqual(task["task"]["approval_scope"], APPROVAL_SCOPE_NONE)
        self.assertEqual(task["task"]["task_kind"], "workflow_task")
        self.assertFalse(task["approvals"])
        self.assertTrue(any(step["tool_id"] == "file.read" and step["status"] == "completed" for step in task["steps"]))
        self.assertTrue(any(item["kind"] == "execution" for item in task["timeline"]))

    async def test_manual_device_support_defaults_to_support_lane(self):
        task = await create_task("Printer cleanup and Teams lag")
        self.assertEqual(task["task"]["task_kind"], "support_incident")
        self.assertEqual(task["task"]["support_severity"], "action_required")

        support_tasks = await list_tasks(task_kind="support_incident")
        workflow_tasks = await list_tasks(task_kind="workflow_task")
        self.assertTrue(any(item["id"] == task["task"]["id"] for item in support_tasks))
        self.assertFalse(any(item["id"] == task["task"]["id"] for item in workflow_tasks))

    async def test_task_level_approval_blocks_until_approved(self):
        task = await create_task("Build the project and generate artifacts")
        self.assertEqual(task["task"]["status"], TASK_STATUS_PLAN_PENDING)
        self.assertEqual(task["task"]["assigned_executor"], "openclaw_executor")
        self.assertEqual(task["task"]["approval_scope"], APPROVAL_SCOPE_TASK)
        self.assertEqual(len(task["approvals"]), 1)
        self.assertEqual(task["approvals"][0]["status"], APPROVAL_STATUS_PENDING)
        self.assertFalse(any(item["kind"] == "execution" for item in task["timeline"]))

        approved = await resolve_approval(task["task"]["id"], task["approvals"][0]["id"], True)
        self.assertEqual(approved["task"]["status"], TASK_STATUS_COMPLETED)
        self.assertTrue(any(item["kind"] == "tool" and "openclaw_executor" in item["title"] for item in approved["timeline"]))

    async def test_privileged_boundary_requires_separate_approval(self):
        task = await create_task("Cleanup startup services on a slow machine")
        approved = await resolve_approval(task["task"]["id"], task["approvals"][0]["id"], True)
        self.assertEqual(approved["task"]["status"], TASK_STATUS_BOUNDARY_APPROVAL_REQUIRED)

        boundary = next(
            approval for approval in approved["approvals"] if approval["approval_scope"] == APPROVAL_SCOPE_BOUNDARY and approval["status"] == APPROVAL_STATUS_PENDING
        )
        rejected = await resolve_approval(approved["task"]["id"], boundary["id"], False)
        self.assertEqual(rejected["task"]["status"], TASK_STATUS_REJECTED)
        self.assertTrue(any(item["kind"] == "approval" and "boundary rejected" in item["title"] for item in rejected["timeline"]))

    async def test_executor_registry_and_reporting_contract(self):
        registry = executor_registry_payload()
        ids = {item["id"] for item in registry}
        self.assertEqual(
            ids,
            {"local_device_executor", "local_dev_executor", "openclaw_executor", "wraith_executor"},
        )
        self.assertTrue(all("result_contract" in item for item in registry))

        task = await create_task("Run recon for the target")
        completed = await resolve_approval(task["task"]["id"], task["approvals"][0]["id"], True)
        self.assertEqual(completed["task"]["assigned_executor"], "wraith_executor")
        self.assertEqual(completed["task"]["status"], TASK_STATUS_COMPLETED)
        self.assertTrue(any(item["kind"] == "tool" and "wraith_executor" in item["title"] for item in completed["timeline"]))

    async def test_channel_message_resolves_and_reuses_session(self):
        first = await receive_channel_message(
            ChannelMessageRequest(
                channel_type="telegram",
                channel_user_id="user-1",
                channel_thread_id="thread-a",
                content="Printer issue and cleanup needed",
            )
        )
        second = await receive_channel_message(
            ChannelMessageRequest(
                channel_type="telegram",
                channel_user_id="user-1",
                channel_thread_id="thread-a",
                content="Printer issue follow-up",
            )
        )
        self.assertEqual(first["conversation_id"], second["conversation_id"])
        self.assertIn("Task:", first["reply"])

        async with aiosqlite.connect(database.get_db_path()) as db:
            async with db.execute(
                "SELECT channel_type, channel_user_id, channel_thread_id FROM conversations WHERE id = ?",
                (first["conversation_id"],),
            ) as cur:
                row = await cur.fetchone()
        self.assertEqual(row, ("telegram", "user-1", "thread-a"))

    async def test_telegram_webhook_creates_session_and_task(self):
        update = {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 777, "type": "private"},
                "from": {"id": 555},
                "text": "Build the project and generate artifacts",
            },
        }
        with patch("routers.channels.send_telegram_message") as send_mock:
            result = await receive_telegram_webhook(update, None)
        self.assertTrue(result["ok"])
        self.assertTrue(result["task_handoff"])
        send_mock.assert_called_once()

    async def test_support_daemon_rule_evaluation(self):
        issues = evaluate_support_snapshot(
            SupportSnapshot(
                disk_used_pct=86.0,
                cpu_load_pct=78.0,
                teams_cpu_pct=30.0,
                active_connections=450,
                mem_used_pct=82.0,
                printer_ready=False,
            )
        )
        keys = {issue.key for issue in issues}
        self.assertEqual(keys, {"disk_pressure", "performance_pressure", "meeting_app_pressure", "printer_network_readiness"})

    async def test_support_persistence_exposes_fix_queue_and_escalations(self):
        await _persist_support_issues(
            [
                SupportIssue(
                    key="disk_pressure",
                    category="disk",
                    severity="action_required",
                    title="Disk pressure",
                    summary="Disk is nearly full.",
                    prompt="Review disk pressure and cleanup candidates.",
                    recommended_fixes=["review cache", "inspect downloads"],
                    auto_fix_kind="queue_cleanup_candidates",
                ),
                SupportIssue(
                    key="camera_audio_readiness",
                    category="camera_audio",
                    severity="escalated",
                    title="Camera and audio readiness",
                    summary="Media service signal is missing.",
                    prompt="Inspect media readiness.",
                    recommended_fixes=["check permissions"],
                    escalation_reason="Permission-sensitive support path.",
                ),
            ]
        )
        status = await support_daemon_status()
        self.assertEqual(status["summary"]["queued_fix_count"], 1)
        self.assertEqual(status["summary"]["escalation_count"], 1)
        self.assertEqual(status["fix_queue"][0]["support_severity"], "fix_queued")
        self.assertEqual(status["escalations"][0]["support_severity"], "escalated")
