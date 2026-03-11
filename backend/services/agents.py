from __future__ import annotations

from typing import Any


AGENT_ROLES = ("planner", "executor", "reviewer")


def build_agent_state(task: dict[str, Any] | None) -> dict[str, Any]:
    if not task:
        return {
            "active_role": "planner",
            "summary": "Waiting for a task.",
            "agents": _agents("idle", "idle", "idle"),
        }

    status = task["task"]["status"]
    executor = task["task"].get("assigned_executor", "local_device_executor")
    if status in {"plan_pending", "boundary_approval_required"}:
        return {
            "active_role": "reviewer",
            "summary": f"Task is blocked pending approval for {executor}.",
            "agents": _agents("planned", "blocked", "waiting_approval"),
        }
    if status == "running":
        return {
            "active_role": "executor",
            "summary": f"Executing through {executor}.",
            "agents": _agents("done", "running", "monitoring"),
        }
    if status == "completed":
        return {
            "active_role": "reviewer",
            "summary": "Task finished and is ready for review.",
            "agents": _agents("done", "done", "summarizing"),
        }
    if status == "failed":
        return {
            "active_role": "reviewer",
            "summary": "Task failed and needs review.",
            "agents": _agents("done", "failed", "reviewing_failure"),
        }
    return {
        "active_role": "planner",
        "summary": f"Task is being planned for {executor}.",
        "agents": _agents("planning", "waiting", "waiting"),
    }


def _agents(planner: str, executor: str, reviewer: str) -> list[dict[str, str]]:
    values = (planner, executor, reviewer)
    return [{"role": role, "state": state} for role, state in zip(AGENT_ROLES, values)]
