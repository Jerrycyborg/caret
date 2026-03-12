from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import aiosqlite

from database import get_db_path
from services.agents import build_agent_state
from services.executors import execute_executor
from services.tool_registry import WORKSPACE_ROOT, execute_tool, get_tool_policy, serialize_json

TASK_STATUS_DRAFT = "draft"
TASK_STATUS_PLAN_PENDING = "plan_pending"
TASK_STATUS_PLAN_APPROVED = "plan_approved"
TASK_STATUS_BOUNDARY_APPROVAL_REQUIRED = "boundary_approval_required"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_REJECTED = "rejected"

STEP_STATUS_PROPOSED = "proposed"
STEP_STATUS_AWAITING_APPROVAL = "awaiting_approval"
STEP_STATUS_RUNNING = "running"
STEP_STATUS_COMPLETED = "completed"
STEP_STATUS_FAILED = "failed"
STEP_STATUS_REJECTED = "rejected"

APPROVAL_STATUS_PENDING = "pending"
APPROVAL_STATUS_APPROVED = "approved"
APPROVAL_STATUS_REJECTED = "rejected"
APPROVAL_SCOPE_NONE = "none"
APPROVAL_SCOPE_TASK = "task"
APPROVAL_SCOPE_BOUNDARY = "boundary"

READ_RISK = "read"
WRITE_RISK = "write"
PRIVILEGED_RISK = "privileged"


@dataclass
class StepDraft:
    title: str
    description: str
    tool_id: str | None
    payload: dict[str, Any]
    risk_level: str
    rollback_note: str
    reason: str
    target: str
    source: str = "oxy"

    @property
    def approval_required(self) -> bool:
        return self.risk_level == PRIVILEGED_RISK


@dataclass
class PlanDraft:
    prompt_class: str
    task_class: str
    execution_domain: str
    reporting_target: str
    approval_scope: str
    assigned_executor: str
    result_channel: str
    title: str
    summary: str
    risk_level: str
    next_suggested_action: str
    steps: list[StepDraft]


def should_plan_task(prompt: str) -> bool:
    lower = prompt.lower()
    return any(
        token in lower
        for token in (
            "printer",
            "teams",
            "zoom",
            "cleanup",
            "slow",
            "lag",
            "build",
            "repo",
            "project",
            "code",
            "review",
            "recon",
            "black-box",
            "white-box",
            "campaign",
            "security",
            "test",
            "inspect",
            "status",
            "search ",
            "write ",
            "run ",
            "firewall",
            "service ",
            "process ",
            "user ",
        )
    )


async def list_tasks(task_kind: str | None = None) -> list[dict[str, Any]]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT id, title, summary, prompt, task_class, execution_domain, reporting_target,
                   approval_scope, assigned_executor, result_channel, task_kind,
                   support_category, support_severity, support_decision_reason,
                   support_recommended_fixes_json, support_source_signal,
                   support_detected_at, support_last_decision_at, trigger_source,
                   auto_fix_eligible, auto_fix_attempted, auto_fix_result,
                   external_ticket_system, external_ticket_key, external_ticket_url,
                   external_ticket_status, external_ticket_created_at,
                   risk_level, next_suggested_action, status, conversation_id, workspace_root,
                   created_at, updated_at
            FROM tasks
        """
        params: tuple[Any, ...] = ()
        if task_kind:
            query += " WHERE task_kind = ?"
            params = (task_kind,)
        query += " ORDER BY updated_at DESC"
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def create_task(
    prompt: str,
    conversation_id: str | None = None,
    task_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task_context = task_context or {}
    plan = plan_prompt(prompt)
    default_task_kind = task_context.get("task_kind") or ("support_incident" if plan.task_class == "device_support" else "workflow_task")
    default_support_severity = task_context.get("support_severity") or ("action_required" if default_task_kind == "support_incident" else "healthy")
    normalized_steps = [_normalize_step(step) for step in plan.steps]
    plan = PlanDraft(
        prompt_class=plan.prompt_class,
        task_class=plan.task_class,
        execution_domain=plan.execution_domain,
        reporting_target=plan.reporting_target,
        approval_scope=_plan_approval_scope(normalized_steps, plan.approval_scope),
        assigned_executor=plan.assigned_executor,
        result_channel=plan.result_channel,
        title=plan.title,
        summary=plan.summary,
        risk_level=_aggregate_risk(normalized_steps),
        next_suggested_action=plan.next_suggested_action,
        steps=normalized_steps,
    )
    task_id = str(uuid.uuid4())
    step_ids = [str(uuid.uuid4()) for _ in plan.steps]

    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            INSERT INTO tasks (
                id, conversation_id, prompt, title, summary, task_class, execution_domain,
                reporting_target, approval_scope, assigned_executor, result_channel, task_kind,
                support_category, support_severity, support_decision_reason, support_recommended_fixes_json,
                support_source_signal, support_detected_at, support_last_decision_at, trigger_source,
                auto_fix_eligible, auto_fix_attempted, auto_fix_result,
                external_ticket_system, external_ticket_key, external_ticket_url,
                external_ticket_status, external_ticket_created_at, risk_level,
                next_suggested_action, status, workspace_root
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                conversation_id,
                prompt,
                plan.title,
                plan.summary,
                plan.task_class,
                plan.execution_domain,
                plan.reporting_target,
                plan.approval_scope,
                plan.assigned_executor,
                plan.result_channel,
                default_task_kind,
                task_context.get("support_category"),
                default_support_severity,
                task_context.get("support_decision_reason", ""),
                serialize_json(task_context.get("support_recommended_fixes", [])),
                task_context.get("support_source_signal", ""),
                task_context.get("support_detected_at"),
                task_context.get("support_last_decision_at"),
                task_context.get("trigger_source", "manual"),
                1 if task_context.get("auto_fix_eligible") else 0,
                1 if task_context.get("auto_fix_attempted") else 0,
                task_context.get("auto_fix_result", ""),
                task_context.get("external_ticket_system", ""),
                task_context.get("external_ticket_key", ""),
                task_context.get("external_ticket_url", ""),
                task_context.get("external_ticket_status", ""),
                task_context.get("external_ticket_created_at"),
                plan.risk_level,
                plan.next_suggested_action,
                TASK_STATUS_DRAFT,
                str(WORKSPACE_ROOT),
            ),
        )
        for position, step in enumerate(plan.steps, start=1):
            depends_on_step_id = step_ids[position - 2] if position > 1 else None
            await db.execute(
                """
                INSERT INTO task_steps (
                    id, task_id, position, title, description, tool_id, risk_level,
                    approval_required, depends_on_step_id, status, payload_json, rollback_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_ids[position - 1],
                    task_id,
                    position,
                    step.title,
                    step.description,
                    step.tool_id,
                    step.risk_level,
                    1 if step.approval_required else 0,
                    depends_on_step_id,
                    STEP_STATUS_PROPOSED,
                    serialize_json({**step.payload, "source": step.source}),
                    step.rollback_note,
                ),
            )
        await _insert_policy_event(
            db,
            task_id,
            None,
            "task_created",
            f"Task planned for {plan.execution_domain} using {plan.assigned_executor}.",
            {
                "prompt": prompt,
                "task_class": plan.task_class,
                "execution_domain": plan.execution_domain,
                "approval_scope": plan.approval_scope,
                "assigned_executor": plan.assigned_executor,
                "task_kind": default_task_kind,
                "support_category": task_context.get("support_category"),
                "support_severity": default_support_severity,
            },
        )
        if plan.approval_scope == APPROVAL_SCOPE_TASK:
            await db.execute(
                "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                (
                    TASK_STATUS_PLAN_PENDING,
                    f"Approve the {plan.task_class} plan to start execution.",
                    task_id,
                ),
            )
            await db.execute(
                """
                INSERT INTO approvals (
                    id, task_id, step_id, label, target, tool_name, risk_level, approval_scope,
                    reason, rollback_note, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    step_ids[0],
                    "Approve task plan",
                    plan.execution_domain,
                    plan.assigned_executor,
                    plan.risk_level,
                    APPROVAL_SCOPE_TASK,
                    f"Task-level approval for {plan.task_class}.",
                    "Review the planned steps before approval.",
                    APPROVAL_STATUS_PENDING,
                ),
            )
        else:
            await db.execute(
                "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (TASK_STATUS_PLAN_APPROVED, task_id),
            )
        await db.commit()

    if plan.approval_scope == APPROVAL_SCOPE_NONE:
        await advance_task(task_id)
    task = await get_task(task_id)
    await _sync_conversation_state(conversation_id, task)
    await _sync_conversation_report(conversation_id, task, "task_created")
    return task


async def maybe_create_task(prompt: str, conversation_id: str | None = None) -> dict[str, Any] | None:
    if not should_plan_task(prompt):
        return None
    task = await create_task(prompt, conversation_id)
    task_info = task["task"]
    completed_reads = [step["title"] for step in task["steps"] if step["status"] == STEP_STATUS_COMPLETED][:3]
    return {
        "task_id": task_info["id"],
        "title": task_info["title"],
        "summary": task_info["summary"],
        "task_kind": task_info["task_kind"],
        "task_class": task_info["task_class"],
        "execution_domain": task_info["execution_domain"],
        "assigned_executor": task_info["assigned_executor"],
        "risk_level": task_info["risk_level"],
        "status": task_info["status"],
        "next_suggested_action": task["next_suggested_action"],
        "result_summary": "Auto-ran: " + ", ".join(completed_reads) if completed_reads else "",
        "agent_state": task["agent_state"],
        "task_report": task["task_report"],
    }


async def get_task(task_id: str) -> dict[str, Any]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        task = await _fetch_task_row(db, task_id)
        if not task:
            raise ValueError("Task not found.")
        steps = await _fetch_task_steps(db, task_id)
        approvals = await _fetch_rows(db, "SELECT * FROM approvals WHERE task_id = ? ORDER BY created_at ASC", (task_id,))
        executions = await _fetch_rows(db, "SELECT * FROM executions WHERE task_id = ? ORDER BY created_at ASC", (task_id,))
        tool_runs = await _fetch_rows(
            db,
            """
            SELECT tr.*, e.step_id
            FROM tool_runs tr
            JOIN executions e ON e.id = tr.execution_id
            WHERE e.task_id = ?
            ORDER BY tr.created_at ASC
            """,
            (task_id,),
        )
        policy_events = await _fetch_rows(db, "SELECT * FROM policy_events WHERE task_id = ? ORDER BY created_at ASC", (task_id,))
    task_payload = _task_payload(dict(task))
    return {
        "task": task_payload,
        "steps": steps,
        "approvals": approvals,
        "timeline": build_timeline(executions, approvals, policy_events, tool_runs),
        "next_suggested_action": task["next_suggested_action"],
        "agent_state": build_agent_state({"task": task_payload, "steps": steps}),
        "task_report": build_task_report(task_payload, steps, approvals),
    }


async def resolve_approval(task_id: str, approval_id: str, approved: bool) -> dict[str, Any]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        approval = await _fetch_one(db, "SELECT * FROM approvals WHERE id = ? AND task_id = ?", (approval_id, task_id))
        if not approval:
            raise ValueError("Approval not found.")
        if approval["status"] != APPROVAL_STATUS_PENDING:
            raise ValueError("Approval is no longer pending.")

        await db.execute(
            "UPDATE approvals SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (APPROVAL_STATUS_APPROVED if approved else APPROVAL_STATUS_REJECTED, approval_id),
        )

        if approval["approval_scope"] == APPROVAL_SCOPE_TASK:
            if approved:
                await db.execute(
                    "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                    (TASK_STATUS_PLAN_APPROVED, "Plan approved. Starting supervised execution.", task_id),
                )
                await _insert_policy_event(db, task_id, approval["step_id"], "plan_approved", "Task-level plan approved.", {})
            else:
                await db.execute(
                    "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                    (TASK_STATUS_REJECTED, "Task plan rejected.", task_id),
                )
                await _insert_policy_event(db, task_id, approval["step_id"], "plan_rejected", "Task-level plan rejected.", {})
        else:
            step = await _fetch_step_row(db, approval["step_id"])
            if not step:
                raise ValueError("Step not found.")
            if approved:
                await db.execute(
                    "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
                    (STEP_STATUS_PROPOSED, approval["step_id"]),
                )
                await db.execute(
                    "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                    (TASK_STATUS_PLAN_APPROVED, f"Boundary approved for {step['title']}.", task_id),
                )
                await _insert_policy_event(db, task_id, approval["step_id"], "boundary_approved", "Privileged boundary approved.", {})
            else:
                await db.execute(
                    "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
                    (STEP_STATUS_REJECTED, approval["step_id"]),
                )
                await db.execute(
                    "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                    (TASK_STATUS_REJECTED, "Privileged boundary rejected.", task_id),
                )
                await _insert_policy_event(db, task_id, approval["step_id"], "boundary_rejected", "Privileged boundary rejected.", {})
        await db.commit()

    if approved:
        await advance_task(task_id)
    task = await get_task(task_id)
    await _sync_conversation_state(task["task"]["conversation_id"], task)
    await _sync_conversation_report(task["task"]["conversation_id"], task, "approval_resolved")
    return task


async def retry_step(task_id: str, step_id: str) -> dict[str, Any]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        step = await _fetch_step_row(db, step_id)
        if not step or step["task_id"] != task_id:
            raise ValueError("Step not found.")
        if step["status"] != STEP_STATUS_FAILED or step["risk_level"] != READ_RISK:
            raise ValueError("Only failed read steps can be retried.")
        await db.execute(
            "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (STEP_STATUS_PROPOSED, step_id),
        )
        await db.execute(
            "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
            (TASK_STATUS_PLAN_APPROVED, "Retrying a failed read step.", task_id),
        )
        await _insert_policy_event(db, task_id, step_id, "step_retry_requested", "Retry requested for a read step.", {})
        await db.commit()
    await advance_task(task_id)
    task = await get_task(task_id)
    await _sync_conversation_state(task["task"]["conversation_id"], task)
    await _sync_conversation_report(task["task"]["conversation_id"], task, "retry_requested")
    return task


async def advance_task(task_id: str) -> None:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        task = await _fetch_task_row(db, task_id)
        if not task or task["status"] in {TASK_STATUS_PLAN_PENDING, TASK_STATUS_REJECTED, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED}:
            return

        while True:
            task = await _fetch_task_row(db, task_id)
            step = await _next_open_step(db, task_id)
            if not step:
                await db.execute(
                    "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                    (TASK_STATUS_COMPLETED, "Task completed. Review the session summary.", task_id),
                )
                await _insert_policy_event(db, task_id, None, "task_completed", "Task completed successfully.", {})
                await db.commit()
                return

            if step["risk_level"] == PRIVILEGED_RISK:
                if await _pending_boundary_exists(db, step["id"]):
                    await db.execute(
                        "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                        (TASK_STATUS_BOUNDARY_APPROVAL_REQUIRED, f"Boundary approval required for {step['title']}.", task_id),
                    )
                    await db.commit()
                    return

                await db.execute(
                    "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
                    (STEP_STATUS_AWAITING_APPROVAL, step["id"]),
                )
                await db.execute(
                    """
                    INSERT INTO approvals (
                        id, task_id, step_id, label, target, tool_name, risk_level, approval_scope,
                        reason, rollback_note, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        task_id,
                        step["id"],
                        f"Boundary approval for {step['title']}",
                        _step_target(step),
                        step["tool_id"] or "rust.delegate",
                        step["risk_level"],
                        APPROVAL_SCOPE_BOUNDARY,
                        _step_reason(step),
                        step["rollback_note"] or "",
                        APPROVAL_STATUS_PENDING,
                    ),
                )
                await db.execute(
                    "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                    (TASK_STATUS_BOUNDARY_APPROVAL_REQUIRED, f"Approve privileged boundary for {step['title']}.", task_id),
                )
                await _insert_policy_event(db, task_id, step["id"], "boundary_required", "Privileged boundary requires approval.", {})
                await db.commit()
                return

            await db.execute(
                "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (STEP_STATUS_RUNNING, step["id"]),
            )
            await db.execute(
                "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                (TASK_STATUS_RUNNING, f"Running {step['title']} via {task['assigned_executor']}.", task_id),
            )
            await db.commit()

            if not await _execute_step(dict(task), dict(step)):
                return


def plan_prompt(prompt: str) -> PlanDraft:
    text = prompt.strip()
    lower = text.lower()
    task_class = _classify_task(text, lower)
    execution_domain, assigned_executor = _route_task(task_class)
    steps = _steps_for_task_class(task_class, text, lower, assigned_executor)
    return PlanDraft(
        prompt_class=task_class,
        task_class=task_class,
        execution_domain=execution_domain,
        reporting_target="oxy",
        approval_scope=_plan_approval_scope(steps, APPROVAL_SCOPE_NONE),
        assigned_executor=assigned_executor,
        result_channel="session",
        title=_build_title(prompt),
        summary=_build_summary(task_class, steps, assigned_executor),
        risk_level=_aggregate_risk(steps),
        next_suggested_action=_next_action(task_class, steps),
        steps=steps,
    )


def build_timeline(
    executions: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    policy_events: list[dict[str, Any]],
    tool_runs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for event in policy_events:
        timeline.append({"kind": "policy", "timestamp": event["created_at"], "title": event["event_type"], "detail": event["message"]})
    for approval in approvals:
        timeline.append(
            {
                "kind": "approval",
                "timestamp": approval["updated_at"],
                "title": f"{approval['approval_scope']} {approval['status']}",
                "detail": approval["label"],
            }
        )
    for execution in executions:
        timeline.append({"kind": "execution", "timestamp": execution["created_at"], "title": execution["status"], "detail": execution["summary"]})
    for tool_run in tool_runs:
        output = json.loads(tool_run["output_json"]) if isinstance(tool_run["output_json"], str) else tool_run["output_json"]
        artifacts = output.get("artifacts", {})
        kind = artifacts.get("executor_id", tool_run["tool_id"])
        timeline.append({"kind": "tool", "timestamp": tool_run["created_at"], "title": kind, "detail": output.get("user_message", tool_run["tool_id"])})
    return sorted(timeline, key=lambda item: item["timestamp"])


def build_task_report(
    task: dict[str, Any],
    steps: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
) -> dict[str, Any]:
    pending = [approval for approval in approvals if approval["status"] == APPROVAL_STATUS_PENDING]
    completed = [step["title"] for step in steps if step["status"] == STEP_STATUS_COMPLETED]
    status = task["status"]
    if status == TASK_STATUS_PLAN_PENDING:
        headline = f"{task['title']} is ready for plan approval."
    elif status == TASK_STATUS_BOUNDARY_APPROVAL_REQUIRED:
        headline = f"{task['title']} is blocked at a privileged boundary."
    elif status == TASK_STATUS_RUNNING:
        headline = f"{task['title']} is running under {task['assigned_executor']}."
    elif status == TASK_STATUS_COMPLETED:
        headline = f"{task['title']} completed under {task['assigned_executor']}."
    elif status == TASK_STATUS_REJECTED:
        headline = f"{task['title']} was rejected."
    elif status == TASK_STATUS_FAILED:
        headline = f"{task['title']} failed."
    else:
        headline = f"{task['title']} is planned."
    details = [
        f"class={task['task_class']} domain={task['execution_domain']} executor={task['assigned_executor']}",
    ]
    if completed:
        details.append("completed: " + ", ".join(completed[:3]))
    if pending:
        details.append("pending approval: " + ", ".join(approval["label"] for approval in pending[:2]))
    details.append(task["next_suggested_action"])
    return {
        "status": status,
        "headline": headline,
        "details": details,
    }


def render_task_report(report: dict[str, Any]) -> str:
    lines = [report["headline"]]
    lines.extend(f"- {detail}" for detail in report["details"])
    return "\n".join(lines)


async def _execute_step(task: dict[str, Any], step: dict[str, Any]) -> bool:
    execution_id = str(uuid.uuid4())
    payload = json.loads(step["payload_json"])
    source = payload.get("source", "oxy")
    try:
        if task["assigned_executor"] in {"openclaw_executor", "wraith_executor"} and source == task["assigned_executor"]:
            output = await execute_executor(task["assigned_executor"], task, step)
        elif step["tool_id"]:
            output = await execute_tool(step["tool_id"], payload)
        else:
            output = {
                "status": "ok",
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
                "artifacts": {"source": source},
                "user_message": step["description"],
            }
        summary = output.get("user_message", f"{step['title']} completed.")
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute("UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?", (STEP_STATUS_COMPLETED, step["id"]))
            await db.execute(
                "INSERT INTO executions (id, task_id, step_id, status, summary) VALUES (?, ?, ?, ?, ?)",
                (execution_id, task["id"], step["id"], "completed", summary),
            )
            await db.execute(
                "INSERT INTO tool_runs (id, execution_id, tool_id, input_json, output_json) VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    execution_id,
                    step["tool_id"] or task["assigned_executor"],
                    serialize_json(payload),
                    serialize_json(output),
                ),
            )
            await _insert_policy_event(db, task["id"], step["id"], "execution_completed", summary, {"executor": task["assigned_executor"], "source": source})
            await db.commit()
        return True
    except Exception as exc:
        summary = f"{step['title']} failed: {exc}"
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute("UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?", (STEP_STATUS_FAILED, step["id"]))
            await db.execute(
                "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                (TASK_STATUS_FAILED, "Task failed. Review execution summary.", task["id"]),
            )
            await db.execute(
                "INSERT INTO executions (id, task_id, step_id, status, summary) VALUES (?, ?, ?, ?, ?)",
                (execution_id, task["id"], step["id"], "failed", summary),
            )
            await db.execute(
                "INSERT INTO tool_runs (id, execution_id, tool_id, input_json, output_json) VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    execution_id,
                    step["tool_id"] or task["assigned_executor"],
                    serialize_json(payload),
                    serialize_json({"status": "failed", "stderr": str(exc), "user_message": summary}),
                ),
            )
            await _insert_policy_event(db, task["id"], step["id"], "execution_failed", summary, {"executor": task["assigned_executor"]})
            await db.commit()
        return False


async def _fetch_task_row(db: aiosqlite.Connection, task_id: str):
    async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cur:
        return await cur.fetchone()


async def _fetch_step_row(db: aiosqlite.Connection, step_id: str):
    async with db.execute("SELECT * FROM task_steps WHERE id = ?", (step_id,)) as cur:
        return await cur.fetchone()


async def _fetch_rows(db: aiosqlite.Connection, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def _fetch_one(db: aiosqlite.Connection, query: str, params: tuple[Any, ...]):
    async with db.execute(query, params) as cur:
        return await cur.fetchone()


async def _fetch_task_steps(db: aiosqlite.Connection, task_id: str) -> list[dict[str, Any]]:
    rows = await _fetch_rows(db, "SELECT * FROM task_steps WHERE task_id = ? ORDER BY position ASC", (task_id,))
    for row in rows:
        row["payload_json"] = json.loads(row["payload_json"])
    return rows


async def _next_open_step(db: aiosqlite.Connection, task_id: str):
    async with db.execute(
        "SELECT * FROM task_steps WHERE task_id = ? AND status IN (?, ?) ORDER BY position ASC",
        (task_id, STEP_STATUS_PROPOSED, STEP_STATUS_AWAITING_APPROVAL),
    ) as cur:
        rows = await cur.fetchall()
    for row in rows:
        if row["status"] == STEP_STATUS_AWAITING_APPROVAL:
            continue
        depends_on = row["depends_on_step_id"]
        if not depends_on:
            return row
        dependency = await _fetch_step_row(db, depends_on)
        if dependency and dependency["status"] == STEP_STATUS_COMPLETED:
            return row
    return None


async def _pending_boundary_exists(db: aiosqlite.Connection, step_id: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM approvals WHERE step_id = ? AND approval_scope = ? AND status = ? LIMIT 1",
        (step_id, APPROVAL_SCOPE_BOUNDARY, APPROVAL_STATUS_PENDING),
    ) as cur:
        row = await cur.fetchone()
    return row is not None


async def _insert_policy_event(
    db: aiosqlite.Connection,
    task_id: str,
    step_id: str | None,
    event_type: str,
    message: str,
    metadata: dict[str, Any],
) -> None:
    await db.execute(
        "INSERT INTO policy_events (id, task_id, step_id, event_type, message, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), task_id, step_id, event_type, message, serialize_json(metadata)),
    )


def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task["id"],
        "title": task["title"],
        "summary": task["summary"],
        "prompt": task["prompt"],
        "task_class": task["task_class"],
        "execution_domain": task["execution_domain"],
        "reporting_target": task["reporting_target"],
        "approval_scope": task["approval_scope"],
        "assigned_executor": task["assigned_executor"],
        "result_channel": task["result_channel"],
        "task_kind": task["task_kind"],
        "support_category": task["support_category"],
        "support_severity": task["support_severity"],
        "support_decision_reason": task["support_decision_reason"],
        "support_recommended_fixes": json.loads(task["support_recommended_fixes_json"] or "[]"),
        "support_source_signal": task["support_source_signal"],
        "support_detected_at": task["support_detected_at"],
        "support_last_decision_at": task["support_last_decision_at"],
        "trigger_source": task["trigger_source"],
        "auto_fix_eligible": bool(task["auto_fix_eligible"]),
        "auto_fix_attempted": bool(task["auto_fix_attempted"]),
        "auto_fix_result": task["auto_fix_result"],
        "external_ticket_system": task["external_ticket_system"],
        "external_ticket_key": task["external_ticket_key"],
        "external_ticket_url": task["external_ticket_url"],
        "external_ticket_status": task["external_ticket_status"],
        "external_ticket_created_at": task["external_ticket_created_at"],
        "risk_level": task["risk_level"],
        "next_suggested_action": task["next_suggested_action"],
        "status": task["status"],
        "conversation_id": task["conversation_id"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }


async def _sync_conversation_state(conversation_id: str | None, task: dict[str, Any]) -> None:
    if not conversation_id:
        return
    agent_state = build_agent_state(task)
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            UPDATE conversations
            SET last_task_id = ?, last_executor = ?, last_agent_state = ?, session_status = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                task["task"]["id"],
                task["task"]["assigned_executor"],
                serialize_json(agent_state),
                _session_status_for_task(task["task"]["status"]),
                conversation_id,
            ),
        )
        await db.commit()


async def _sync_conversation_report(conversation_id: str | None, task: dict[str, Any], event: str) -> None:
    if not conversation_id:
        return
    report = render_task_report(task["task_report"])
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), conversation_id, "assistant", f"[task:{event}]\n{report}"),
        )
        await db.commit()


def _session_status_for_task(task_status: str) -> str:
    if task_status in {TASK_STATUS_PLAN_PENDING, TASK_STATUS_BOUNDARY_APPROVAL_REQUIRED}:
        return "blocked"
    if task_status == TASK_STATUS_RUNNING:
        return "running"
    if task_status == TASK_STATUS_COMPLETED:
        return "completed"
    if task_status in {TASK_STATUS_FAILED, TASK_STATUS_REJECTED}:
        return "failed"
    return "active"


def _build_title(prompt: str) -> str:
    return prompt[:72] + ("…" if len(prompt) > 72 else "")


def _build_summary(task_class: str, steps: list[StepDraft], assigned_executor: str) -> str:
    labels = ", ".join(step.title for step in steps[:2])
    return f"{task_class.replace('_', ' ')} via {assigned_executor}: {labels}."


def _next_action(task_class: str, steps: list[StepDraft]) -> str:
    if any(step.risk_level != READ_RISK for step in steps):
        return f"Review and approve the {task_class.replace('_', ' ')} plan."
    return "Review the auto-run results and decide the next move."


def _aggregate_risk(steps: list[StepDraft]) -> str:
    if any(step.risk_level == PRIVILEGED_RISK for step in steps):
        return PRIVILEGED_RISK
    if any(step.risk_level == WRITE_RISK for step in steps):
        return WRITE_RISK
    return READ_RISK


def _classify_task(text: str, lower: str) -> str:
    if any(token in lower for token in ("recon", "black-box", "black box", "campaign", "exploit")):
        return "security_assessment"
    if any(token in lower for token in ("white-box", "white box", "review", "audit")):
        return "security_review"
    if any(token in lower for token in ("build", "artifact", "compile", "release")):
        return "project_build"
    if any(token in lower for token in ("printer", "teams", "zoom", "cleanup", "slow", "lag", "startup", "network")):
        return "device_support"
    if any(token in lower for token in ("repo", "project", "code", "test", "git", "file", "error", "debug")):
        return "developer_support"
    return "general_local_assistance"


def _route_task(task_class: str) -> tuple[str, str]:
    if task_class == "device_support":
        return "local_device", "local_device_executor"
    if task_class == "project_build":
        return "openclaw", "openclaw_executor"
    if task_class in {"security_assessment", "security_review"}:
        return "wraith", "wraith_executor"
    if task_class == "developer_support":
        return "local_dev", "local_dev_executor"
    return "local_device", "local_device_executor"


def _plan_approval_scope(steps: list[StepDraft], current: str) -> str:
    if any(step.risk_level != READ_RISK for step in steps):
        return APPROVAL_SCOPE_TASK
    return current


def _steps_for_task_class(task_class: str, text: str, lower: str, assigned_executor: str) -> list[StepDraft]:
    if task_class == "device_support":
        steps = [
            _note_step("Inspect device context", "Capture the problem statement and affected device symptoms.", READ_RISK, "device-context", "Summarize the local support problem."),
            _note_step("Run device-support triage", "Prepare supervised device diagnostics and safe fix guidance.", WRITE_RISK, "device-triage", "Device support can lead to supervised changes.", assigned_executor),
        ]
        if any(token in lower for token in ("cleanup", "startup", "service", "process")):
            steps.append(_privileged_step("Escalate local system action", "Prepare a privileged local boundary for supervised device fixes.", {"target": "device_maintenance"}, "Use the Rust security flow if the plan needs system changes.", "Privileged local system changes require a boundary approval.", "device-maintenance"))
        return steps
    if task_class == "project_build":
        return _repo_baseline_steps() + [
            _executor_step("Delegate build workflow", "Send the build/project workflow to OpenClaw under Oxy supervision.", WRITE_RISK, "openclaw-build", "Project builds can mutate artifacts and reports.", assigned_executor),
            _note_step("Review delegated result", "Capture delegated build summary inside Oxy.", READ_RISK, "openclaw-result", "Review the result and decide the next move."),
        ]
    if task_class in {"security_assessment", "security_review"}:
        return [
            _note_step("Scope security request", "Summarize the requested security objective and constraints.", READ_RISK, task_class, "Keep the work bounded and supervised."),
            _executor_step("Delegate security workflow", "Send the security workflow to Wraith and keep reporting in Oxy.", WRITE_RISK, "wraith-task", "Delegated security work requires explicit task approval.", assigned_executor),
            _note_step("Review Wraith findings", "Capture the delegated security summary inside Oxy.", READ_RISK, "wraith-result", "Review findings and decide the next move."),
        ]
    if task_class == "developer_support":
        search_term = _extract_search_term(text)
        steps = _repo_baseline_steps()
        if search_term:
            steps.append(_tool_step("Search workspace", f"Search the workspace for `{search_term}`.", "project.search", {"query": search_term, "cwd": "."}, "No rollback needed for reads.", "Search is read-only.", f"workspace-search:{search_term}"))
        read_path = _extract_path(text, ("read", "open"))
        if read_path:
            steps.append(_tool_step("Read file", f"Read `{read_path}` from the workspace.", "file.read", {"path": read_path}, "No rollback needed for reads.", "File inspection is read-only.", read_path))
        write_request = _extract_write_request(text)
        if write_request:
            path, content = write_request
            steps.append(_tool_step("Write file", f"Write requested content into `{path}`.", "file.write", {"path": path, "content": content}, "Restore the previous file contents from version control or backup.", "Writing files mutates the workspace.", path))
        run_command = _extract_run_command(text)
        if run_command:
            tool_id = "build.run" if _is_build_command(run_command) else "shell.run"
            steps.append(_tool_step("Run command", f"Execute `{run_command}` under supervision.", tool_id, {"command": run_command, "cwd": "."}, "Review command effects and revert changes if needed.", "Commands can mutate the workspace.", run_command))
        return steps
    return [
        _note_step("Summarize request", "Summarize the local assistance request.", READ_RISK, "local-summary", "Keep the work supervised."),
        _note_step("Prepare assisted response", "Prepare the next supervised action for the user.", READ_RISK, "local-next", "Review the summary and choose the next move."),
    ]


def _repo_baseline_steps() -> list[StepDraft]:
    return [
        _tool_step("Inspect repository status", "Gather repository status before any further action.", "git.status", {"cwd": "."}, "No rollback needed for reads.", "Repository inspection is read-only.", "workspace:."),
        _tool_step("List project tree", "List a compact workspace tree for orientation.", "project.tree", {"path": ".", "max_entries": 40}, "No rollback needed for reads.", "Workspace tree inspection is read-only.", "workspace:tree"),
    ]


def _normalize_step(step: StepDraft) -> StepDraft:
    if not step.tool_id:
        return step
    policy = get_tool_policy(step.tool_id)
    return StepDraft(
        title=step.title,
        description=step.description,
        tool_id=step.tool_id,
        payload=step.payload,
        risk_level=policy.risk_level,
        rollback_note=step.rollback_note,
        reason=step.reason,
        target=step.target,
        source=step.source,
    )


def _tool_step(title: str, description: str, tool_id: str, payload: dict[str, Any], rollback_note: str, reason: str, target: str) -> StepDraft:
    policy = get_tool_policy(tool_id)
    return StepDraft(title, description, tool_id, payload, policy.risk_level, rollback_note, reason, target, "oxy")


def _note_step(title: str, description: str, risk_level: str, target: str, reason: str, source: str = "oxy") -> StepDraft:
    return StepDraft(title, description, None, {"target": target}, risk_level, "Review the step summary before proceeding.", reason, target, source)


def _executor_step(title: str, description: str, risk_level: str, target: str, reason: str, source: str) -> StepDraft:
    return StepDraft(title, description, None, {"target": target}, risk_level, "Review delegated work summaries inside Oxy.", reason, target, source)


def _privileged_step(title: str, description: str, payload: dict[str, Any], rollback_note: str, reason: str, target: str) -> StepDraft:
    return StepDraft(title, description, None, payload, PRIVILEGED_RISK, rollback_note, reason, target, "rust")


def _extract_search_term(text: str) -> str | None:
    match = re.search(r"(?:search|find)\s+(?:for\s+)?(.+)", text, re.IGNORECASE)
    return match.group(1).strip()[:120] if match else None


def _extract_path(text: str, verbs: tuple[str, ...]) -> str | None:
    pattern = r"(?:%s)\s+([^\s]+)" % "|".join(re.escape(verb) for verb in verbs)
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_write_request(text: str) -> tuple[str, str] | None:
    match = re.search(r"write\s+([^\s]+)\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    return (match.group(1), match.group(2).strip()) if match else None


def _extract_run_command(text: str) -> str | None:
    match = re.search(r"(?:run|build)\s+(.+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _is_build_command(command: str) -> bool:
    return command.split(" ", 1)[0] in {"npm", "pnpm", "cargo", "python", "python3", "docker"}


def _step_target(step: aiosqlite.Row) -> str:
    payload = json.loads(step["payload_json"])
    return payload.get("path") or payload.get("command") or payload.get("query") or payload.get("target") or "workspace"


def _step_reason(step: aiosqlite.Row) -> str:
    if step["risk_level"] == PRIVILEGED_RISK:
        return "Privileged local OS actions require a boundary approval and Rust execution."
    if step["risk_level"] == WRITE_RISK:
        return "This task plan can mutate local state or delegate work externally."
    return "Read-only action."
