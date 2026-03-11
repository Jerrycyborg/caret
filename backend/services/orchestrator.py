from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import aiosqlite

from database import get_db_path
from services.tool_registry import WORKSPACE_ROOT, execute_tool, registry_payload, serialize_json

TASK_STATUS_DRAFT = "draft"
TASK_STATUS_PROPOSED = "proposed"
TASK_STATUS_AWAITING_APPROVAL = "awaiting_approval"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_DONE = "done"
TASK_STATUS_FAILED = "failed"

STEP_STATUS_DRAFT = "draft"
STEP_STATUS_PROPOSED = "proposed"
STEP_STATUS_AWAITING_APPROVAL = "awaiting_approval"
STEP_STATUS_RUNNING = "running"
STEP_STATUS_DONE = "done"
STEP_STATUS_FAILED = "failed"
STEP_STATUS_REJECTED = "rejected"

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

    @property
    def approval_required(self) -> bool:
        return self.risk_level != READ_RISK


@dataclass
class PlanDraft:
    prompt_class: str
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
            "inspect",
            "status",
            "diff",
            "read ",
            "open ",
            "write ",
            "run ",
            "build",
            "search ",
            "find ",
            "service ",
            "firewall",
            "user ",
            "process ",
            "repo",
            "project",
        )
    )


async def list_tasks() -> list[dict[str, Any]]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, title, summary, prompt, risk_level, next_suggested_action, status,
                   conversation_id, workspace_root, created_at, updated_at
            FROM tasks
            ORDER BY updated_at DESC
            """
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def create_task(prompt: str, conversation_id: str | None = None) -> dict[str, Any]:
    plan = plan_prompt(prompt)
    task_id = str(uuid.uuid4())
    step_ids = [str(uuid.uuid4()) for _ in plan.steps]

    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            INSERT INTO tasks (
                id, conversation_id, prompt, title, summary, risk_level,
                next_suggested_action, status, workspace_root
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                conversation_id,
                prompt,
                plan.title,
                plan.summary,
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
                    serialize_json(step.payload),
                    step.rollback_note,
                ),
            )
        await db.execute(
            "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (TASK_STATUS_PROPOSED, task_id),
        )
        await _insert_policy_event(
            db,
            task_id,
            None,
            "task_created",
            "Task plan created from prompt.",
            {"prompt": prompt, "risk_level": plan.risk_level},
        )
        await db.commit()

    await advance_task(task_id)
    return await get_task(task_id)


async def maybe_create_task(prompt: str, conversation_id: str | None = None) -> dict[str, Any] | None:
    if not should_plan_task(prompt):
        return None
    task = await create_task(prompt, conversation_id)
    task_info = task["task"]
    completed_reads = [step["title"] for step in task["steps"] if step["status"] == STEP_STATUS_DONE][:3]
    return {
        "task_id": task_info["id"],
        "title": task_info["title"],
        "summary": task_info["summary"],
        "risk_level": task_info["risk_level"],
        "status": task_info["status"],
        "next_suggested_action": task["next_suggested_action"],
        "result_summary": "Auto-ran: " + ", ".join(completed_reads) if completed_reads else "",
    }


async def get_task(task_id: str) -> dict[str, Any]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        task = await _fetch_task_row(db, task_id)
        if not task:
            raise ValueError("Task not found.")
        steps = await _fetch_task_steps(db, task_id)
        approvals = await _fetch_rows(
            db,
            "SELECT * FROM approvals WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        executions = await _fetch_rows(
            db,
            "SELECT * FROM executions WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
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
        policy_events = await _fetch_rows(
            db,
            "SELECT * FROM policy_events WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
    timeline = build_timeline(executions, approvals, policy_events, tool_runs)
    return {
        "task": _task_payload(dict(task)),
        "steps": steps,
        "approvals": approvals,
        "timeline": timeline,
        "next_suggested_action": task["next_suggested_action"],
    }


async def resolve_approval(task_id: str, approval_id: str, approved: bool) -> dict[str, Any]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM approvals WHERE id = ? AND task_id = ?",
            (approval_id, task_id),
        ) as cur:
            approval = await cur.fetchone()
        if not approval:
            raise ValueError("Approval not found.")
        if approval["status"] != "pending":
            raise ValueError("Approval is no longer pending.")

        step = await _fetch_step_row(db, approval["step_id"])
        if not step:
            raise ValueError("Step not found.")

        new_status = "approved" if approved else "rejected"
        await db.execute(
            "UPDATE approvals SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, approval_id),
        )

        if approved and step["risk_level"] == PRIVILEGED_RISK:
            await _mark_privileged_step_delegated(db, task_id, step)
        elif approved:
            await db.execute(
                "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (STEP_STATUS_PROPOSED, approval["step_id"]),
            )
            await db.execute(
                "UPDATE tasks SET status = ?, updated_at = datetime('now'), next_suggested_action = ? WHERE id = ?",
                (TASK_STATUS_PROPOSED, "Task resumed after approval.", task_id),
            )
            await _insert_policy_event(
                db,
                task_id,
                approval["step_id"],
                "approval_resolved",
                "Mutating action approved.",
                {"approval_id": approval_id, "status": new_status},
            )
        else:
            await db.execute(
                "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (STEP_STATUS_REJECTED, approval["step_id"]),
            )
            await db.execute(
                "UPDATE tasks SET status = ?, updated_at = datetime('now'), next_suggested_action = ? WHERE id = ?",
                (TASK_STATUS_FAILED, "Review the rejected step and adjust the task.", task_id),
            )
            await _insert_policy_event(
                db,
                task_id,
                approval["step_id"],
                "approval_resolved",
                "Mutating action rejected.",
                {"approval_id": approval_id, "status": new_status},
            )
        await db.commit()

    if approved and step["risk_level"] != PRIVILEGED_RISK:
        await advance_task(task_id)
    return await get_task(task_id)


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
            "UPDATE tasks SET status = ?, updated_at = datetime('now'), next_suggested_action = ? WHERE id = ?",
            (TASK_STATUS_PROPOSED, "Retrying a failed read step.", task_id),
        )
        await _insert_policy_event(
            db,
            task_id,
            step_id,
            "step_retry_requested",
            "Retry requested for a failed read step.",
            {"step_id": step_id},
        )
        await db.commit()
    await advance_task(task_id)
    return await get_task(task_id)


async def advance_task(task_id: str) -> None:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        while True:
            task = await _fetch_task_row(db, task_id)
            if not task:
                return

            step = await _next_open_step(db, task_id)
            if not step:
                final_status = TASK_STATUS_FAILED if await _task_has_rejection(db, task_id) else TASK_STATUS_DONE
                next_action = (
                    "Task completed. Review results and decide the next move."
                    if final_status == TASK_STATUS_DONE
                    else "Task stopped after a rejection or failure."
                )
                await db.execute(
                    "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                    (final_status, next_action, task_id),
                )
                await _insert_policy_event(
                    db,
                    task_id,
                    None,
                    "task_completed" if final_status == TASK_STATUS_DONE else "task_stopped",
                    "Task finished all planned steps." if final_status == TASK_STATUS_DONE else "Task stopped before completion.",
                    {},
                )
                await db.commit()
                return

            if step["approval_required"]:
                if await _pending_approval_exists(db, step["id"]):
                    await db.execute(
                        "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                        (TASK_STATUS_AWAITING_APPROVAL, f"Review approval for {step['title']}.", task_id),
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
                        id, task_id, step_id, label, target, tool_name, risk_level, reason, rollback_note, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                    """,
                    (
                        str(uuid.uuid4()),
                        task_id,
                        step["id"],
                        step["title"],
                        _step_target(step),
                        step["tool_id"] or "rust.delegate",
                        step["risk_level"],
                        _step_reason(step),
                        step["rollback_note"] or "",
                    ),
                )
                await db.execute(
                    "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                    (TASK_STATUS_AWAITING_APPROVAL, f"Approve or reject {step['title']}.", task_id),
                )
                await _insert_policy_event(
                    db,
                    task_id,
                    step["id"],
                    "approval_required",
                    "Step paused pending approval.",
                    {"tool_id": step["tool_id"], "risk_level": step["risk_level"]},
                )
                await db.commit()
                return

            await db.execute(
                "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                (TASK_STATUS_RUNNING, f"Running {step['title']}.", task_id),
            )
            await db.execute(
                "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (STEP_STATUS_RUNNING, step["id"]),
            )
            await _insert_policy_event(
                db,
                task_id,
                step["id"],
                "auto_allowed",
                "Read-only step executed without approval.",
                {"tool_id": step["tool_id"], "risk_level": step["risk_level"]},
            )
            await db.commit()

            success = await _execute_step(task_id, step["id"])
            if not success:
                return


def plan_prompt(prompt: str) -> PlanDraft:
    text = prompt.strip()
    lower = text.lower()
    prompt_class = _classify_prompt(lower, text)
    steps = _steps_for_prompt_class(prompt_class, text, lower)
    risk_level = _aggregate_risk(steps)
    return PlanDraft(
        prompt_class=prompt_class,
        title=_build_title(prompt),
        summary=_build_summary(prompt_class, steps),
        risk_level=risk_level,
        next_suggested_action="Review approvals if any mutating or privileged steps are proposed.",
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
        timeline.append(
            {
                "kind": "policy",
                "timestamp": event["created_at"],
                "title": event["event_type"],
                "detail": event["message"],
            }
        )
    for approval in approvals:
        timeline.append(
            {
                "kind": "approval",
                "timestamp": approval["updated_at"],
                "title": f"Approval {approval['status']}",
                "detail": approval["label"] or approval["step_id"],
            }
        )
    for execution in executions:
        timeline.append(
            {
                "kind": "execution",
                "timestamp": execution["created_at"],
                "title": execution["status"],
                "detail": execution["summary"],
            }
        )
    for tool_run in tool_runs:
        output = json.loads(tool_run["output_json"]) if isinstance(tool_run["output_json"], str) else tool_run["output_json"]
        timeline.append(
            {
                "kind": "tool",
                "timestamp": tool_run["created_at"],
                "title": tool_run["tool_id"],
                "detail": output.get("user_message", tool_run["tool_id"]),
            }
        )
    return sorted(timeline, key=lambda item: item["timestamp"])


async def _execute_step(task_id: str, step_id: str) -> bool:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        step = await _fetch_step_row(db, step_id)
        if not step:
            return False

        execution_id = str(uuid.uuid4())
        payload = json.loads(step["payload_json"])
        tool_id = step["tool_id"]
        try:
            output = await execute_tool(tool_id, payload) if tool_id else {"status": "ok", "user_message": step["description"]}
            summary = output.get("user_message", f"{tool_id or 'step'} executed successfully.")
            await db.execute(
                "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (STEP_STATUS_DONE, step_id),
            )
            await db.execute(
                "INSERT INTO executions (id, task_id, step_id, status, summary) VALUES (?, ?, ?, ?, ?)",
                (execution_id, task_id, step_id, "done", summary),
            )
            await db.execute(
                "INSERT INTO tool_runs (id, execution_id, tool_id, input_json, output_json) VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    execution_id,
                    tool_id or "note",
                    serialize_json(payload),
                    serialize_json(output),
                ),
            )
            await _insert_policy_event(
                db,
                task_id,
                step_id,
                "execution_completed",
                summary,
                {"tool_id": tool_id, "status": output.get("status", "ok")},
            )
            await db.commit()
            return True
        except Exception as exc:
            summary = f"{tool_id or 'step'} failed: {exc}"
            await db.execute(
                "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (STEP_STATUS_FAILED, step_id),
            )
            await db.execute(
                "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
                (TASK_STATUS_FAILED, "Inspect the failed step and retry if safe.", task_id),
            )
            await db.execute(
                "INSERT INTO executions (id, task_id, step_id, status, summary) VALUES (?, ?, ?, ?, ?)",
                (execution_id, task_id, step_id, "failed", summary),
            )
            await db.execute(
                "INSERT INTO tool_runs (id, execution_id, tool_id, input_json, output_json) VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    execution_id,
                    tool_id or "note",
                    serialize_json(payload),
                    serialize_json({"status": "failed", "stderr": str(exc), "user_message": summary}),
                ),
            )
            await _insert_policy_event(
                db,
                task_id,
                step_id,
                "execution_failed",
                summary,
                {"tool_id": tool_id, "error": str(exc)},
            )
            await db.commit()
            return False


async def _mark_privileged_step_delegated(db: aiosqlite.Connection, task_id: str, step: aiosqlite.Row) -> None:
    execution_id = str(uuid.uuid4())
    summary = f"Privileged step delegated to the Rust security flow for {step['title']}."
    await db.execute(
        "UPDATE task_steps SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (STEP_STATUS_DONE, step["id"]),
    )
    await db.execute(
        "UPDATE tasks SET status = ?, next_suggested_action = ?, updated_at = datetime('now') WHERE id = ?",
        (TASK_STATUS_DONE, "Complete the privileged operation through the Rust security panel.", task_id),
    )
    await db.execute(
        "INSERT INTO executions (id, task_id, step_id, status, summary) VALUES (?, ?, ?, ?, ?)",
        (execution_id, task_id, step["id"], "delegated", summary),
    )
    await db.execute(
        "INSERT INTO tool_runs (id, execution_id, tool_id, input_json, output_json) VALUES (?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            execution_id,
            "rust.delegate",
            step["payload_json"],
            serialize_json({"status": "delegated", "user_message": summary}),
        ),
    )
    await _insert_policy_event(
        db,
        task_id,
        step["id"],
        "privileged_delegated",
        summary,
        {"target": json.loads(step["payload_json"]).get("target", "")},
    )


async def _fetch_task_row(db: aiosqlite.Connection, task_id: str):
    async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cur:
        return await cur.fetchone()


async def _fetch_step_row(db: aiosqlite.Connection, step_id: str):
    async with db.execute("SELECT * FROM task_steps WHERE id = ?", (step_id,)) as cur:
        return await cur.fetchone()


async def _fetch_task_steps(db: aiosqlite.Connection, task_id: str) -> list[dict[str, Any]]:
    rows = await _fetch_rows(
        db,
        "SELECT * FROM task_steps WHERE task_id = ? ORDER BY position ASC",
        (task_id,),
    )
    for row in rows:
        row["payload_json"] = json.loads(row["payload_json"])
    return rows


async def _fetch_rows(db: aiosqlite.Connection, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def _next_open_step(db: aiosqlite.Connection, task_id: str):
    async with db.execute(
        """
        SELECT *
        FROM task_steps
        WHERE task_id = ?
          AND status IN (?, ?)
        ORDER BY position ASC
        """,
        (task_id, STEP_STATUS_DRAFT, STEP_STATUS_PROPOSED),
    ) as cur:
        rows = await cur.fetchall()
    for row in rows:
        depends_on = row["depends_on_step_id"]
        if not depends_on:
            return row
        dependency = await _fetch_step_row(db, depends_on)
        if dependency and dependency["status"] == STEP_STATUS_DONE:
            return row
    return None


async def _pending_approval_exists(db: aiosqlite.Connection, step_id: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM approvals WHERE step_id = ? AND status = 'pending' LIMIT 1",
        (step_id,),
    ) as cur:
        row = await cur.fetchone()
    return row is not None


async def _task_has_rejection(db: aiosqlite.Connection, task_id: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM task_steps WHERE task_id = ? AND status IN (?, ?) LIMIT 1",
        (task_id, STEP_STATUS_REJECTED, STEP_STATUS_FAILED),
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
        """
        INSERT INTO policy_events (id, task_id, step_id, event_type, message, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), task_id, step_id, event_type, message, serialize_json(metadata)),
    )


def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task["id"],
        "title": task["title"],
        "summary": task["summary"],
        "prompt": task["prompt"],
        "risk_level": task["risk_level"],
        "next_suggested_action": task["next_suggested_action"],
        "status": task["status"],
        "conversation_id": task["conversation_id"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }


def _build_title(prompt: str) -> str:
    return prompt[:72] + ("…" if len(prompt) > 72 else "")


def _build_summary(prompt_class: str, steps: list[StepDraft]) -> str:
    labels = ", ".join(step.title for step in steps[:3])
    extra = "" if len(steps) <= 3 else f", +{len(steps) - 3} more"
    return f"{prompt_class.replace('_', ' ')}: {labels}{extra}."


def _aggregate_risk(steps: list[StepDraft]) -> str:
    if any(step.risk_level == PRIVILEGED_RISK for step in steps):
        return PRIVILEGED_RISK
    if any(step.risk_level == WRITE_RISK for step in steps):
        return WRITE_RISK
    return READ_RISK


def _classify_prompt(lower: str, text: str) -> str:
    if _extract_privileged_target(lower):
        return "privileged_request"
    if _extract_write_request(text):
        return "write_requested_file"
    if _extract_run_command(text):
        return "build_then_inspect" if "build" in lower or _is_build_command(_extract_run_command(text) or "") else "repo_inspection"
    if _extract_search_term(text):
        return "search_then_read"
    if "diff" in lower:
        return "diff_inspection"
    return "repo_inspection"


def _steps_for_prompt_class(prompt_class: str, text: str, lower: str) -> list[StepDraft]:
    if prompt_class == "privileged_request":
        target = _extract_privileged_target(lower) or "system"
        return _repo_baseline_steps() + [
            StepDraft(
                title=f"Delegate privileged action for {target}",
                description=f"Prepare a Rust-only privileged action for `{target}`.",
                tool_id=None,
                payload={"target": target},
                risk_level=PRIVILEGED_RISK,
                rollback_note="Use the Rust security flow and verify system state after execution.",
                reason="Privileged OS changes must stay in the Rust bridge.",
                target=target,
            )
        ]
    if prompt_class == "write_requested_file":
        path, content = _extract_write_request(text) or ("README.md", "")
        steps = _repo_baseline_steps()
        steps.append(
            StepDraft(
                title=f"Inspect {path}",
                description=f"Read `{path}` before any write if it already exists.",
                tool_id="project.read_many",
                payload={"paths": [path]},
                risk_level=READ_RISK,
                rollback_note="No rollback needed for reads.",
                reason="Review current file contents before mutating.",
                target=path,
            )
        )
        steps.append(
            StepDraft(
                title=f"Write {path}",
                description=f"Write requested content into `{path}`.",
                tool_id="file.write",
                payload={"path": path, "content": content},
                risk_level=WRITE_RISK,
                rollback_note="Restore the previous file contents from version control or backup.",
                reason="Writing files mutates the workspace.",
                target=path,
            )
        )
        return steps
    if prompt_class == "build_then_inspect":
        command = _extract_run_command(text) or _infer_build_command(text)
        return _repo_baseline_steps() + [
            StepDraft(
                title="Run build command",
                description=f"Execute `{command}` in the workspace.",
                tool_id="build.run",
                payload={"command": command, "cwd": "."},
                risk_level=WRITE_RISK,
                rollback_note="Revert generated artifacts or working tree changes if needed.",
                reason="Build commands can mutate the workspace.",
                target=command,
            ),
            StepDraft(
                title="Review repository diff",
                description="Inspect repository diff after the build step.",
                tool_id="git.diff",
                payload={"cwd": "."},
                risk_level=READ_RISK,
                rollback_note="No rollback needed for reads.",
                reason="Diff inspection shows build side effects.",
                target="git:diff",
            ),
        ]
    if prompt_class == "search_then_read":
        query = _extract_search_term(text) or "TODO"
        read_path = _extract_path(text, ("read", "open"))
        steps = _repo_baseline_steps() + [
            StepDraft(
                title=f"Search workspace for {query}",
                description=f"Search the workspace for `{query}`.",
                tool_id="project.search",
                payload={"query": query, "cwd": "."},
                risk_level=READ_RISK,
                rollback_note="No rollback needed for reads.",
                reason="Search is read-only and narrows the next read.",
                target=f"workspace-search:{query}",
            )
        ]
        if read_path:
            steps.append(
                StepDraft(
                    title=f"Read {read_path}",
                    description=f"Read `{read_path}` from the workspace.",
                    tool_id="file.read",
                    payload={"path": read_path},
                    risk_level=READ_RISK,
                    rollback_note="No rollback needed for reads.",
                    reason="File inspection is read-only.",
                    target=read_path,
                )
            )
        else:
            steps.append(
                StepDraft(
                    title="Read common project files",
                    description="Read a compact set of common project files for context.",
                    tool_id="project.read_many",
                    payload={"paths": _default_read_many_paths()},
                    risk_level=READ_RISK,
                    rollback_note="No rollback needed for reads.",
                    reason="Context gathering remains read-only.",
                    target="workspace:core-files",
                )
            )
        return steps
    if prompt_class == "diff_inspection":
        return _repo_baseline_steps() + [
            StepDraft(
                title="Review repository diff",
                description="Inspect repository diff statistics.",
                tool_id="git.diff",
                payload={"cwd": "."},
                risk_level=READ_RISK,
                rollback_note="No rollback needed for reads.",
                reason="Diff inspection is read-only.",
                target="git:diff",
            ),
            StepDraft(
                title="Review recent commits",
                description="Inspect recent git history for context.",
                tool_id="git.log",
                payload={"cwd": "."},
                risk_level=READ_RISK,
                rollback_note="No rollback needed for reads.",
                reason="Git history is read-only.",
                target="git:log",
            ),
        ]
    return _repo_baseline_steps() + [
        StepDraft(
            title="Review recent commits",
            description="Inspect recent git history for context.",
            tool_id="git.log",
            payload={"cwd": "."},
            risk_level=READ_RISK,
            rollback_note="No rollback needed for reads.",
            reason="Git history is read-only.",
            target="git:log",
        )
    ]


def _repo_baseline_steps() -> list[StepDraft]:
    return [
        StepDraft(
            title="Inspect repository status",
            description="Gather repository status before any further action.",
            tool_id="git.status",
            payload={"cwd": "."},
            risk_level=READ_RISK,
            rollback_note="No rollback needed for reads.",
            reason="Read-only repository inspection is safe to auto-run.",
            target="workspace:.",
        ),
        StepDraft(
            title="List project tree",
            description="List a compact workspace tree for orientation.",
            tool_id="project.tree",
            payload={"path": ".", "max_entries": 40},
            risk_level=READ_RISK,
            rollback_note="No rollback needed for reads.",
            reason="Workspace tree inspection is read-only.",
            target="workspace:tree",
        ),
    ]


def _default_read_many_paths() -> list[str]:
    return ["README.md", "package.json", "src/App.tsx"]


def _extract_search_term(text: str) -> str | None:
    match = re.search(r"(?:search|find)\s+(?:for\s+)?(.+)", text, re.IGNORECASE)
    if not match:
        return None
    query = match.group(1).strip()
    return query[:120] if query else None


def _extract_path(text: str, verbs: tuple[str, ...]) -> str | None:
    pattern = r"(?:%s)\s+([^\s]+)" % "|".join(re.escape(verb) for verb in verbs)
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_write_request(text: str) -> tuple[str, str] | None:
    match = re.search(r"write\s+([^\s]+)\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1), match.group(2).strip()


def _extract_run_command(text: str) -> str | None:
    match = re.search(r"(?:run|build)\s+(.+)", text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _infer_build_command(text: str) -> str:
    lower = text.lower()
    if "cargo" in lower:
        return "cargo build"
    if "python" in lower:
        return "python3 -m pytest"
    return "npm run build"


def _is_build_command(command: str) -> bool:
    return command.split(" ", 1)[0] in {"npm", "pnpm", "cargo", "python", "python3", "docker"}


def _extract_privileged_target(lower: str) -> str | None:
    for token in ("firewall", "service", "user", "process"):
        if token in lower:
            return token
    return None


def _step_target(step: aiosqlite.Row) -> str:
    payload = json.loads(step["payload_json"])
    return payload.get("path") or payload.get("command") or payload.get("query") or payload.get("target") or "workspace"


def _step_reason(step: aiosqlite.Row) -> str:
    if step["risk_level"] == PRIVILEGED_RISK:
        return "Privileged OS actions require Rust-only execution and explicit approval."
    if step["risk_level"] == WRITE_RISK:
        return "This step can mutate the workspace or environment."
    return "Read-only action."
