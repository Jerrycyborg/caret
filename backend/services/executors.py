from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutorDefinition:
    id: str
    role: str
    capabilities: list[str]
    health: str
    supported_task_types: list[str]
    execution_mode: str
    result_contract: dict[str, Any]


def executor_registry() -> list[ExecutorDefinition]:
    return [
        ExecutorDefinition(
            id="local_device_executor",
            role="device_support",
            capabilities=["cleanup_guidance", "printer_network_diagnosis", "app_lag_triage", "safe_fix_notes"],
            health="healthy",
            supported_task_types=["device_support", "general_local_assistance"],
            execution_mode="local_supervised",
            result_contract=_result_contract(),
        ),
        ExecutorDefinition(
            id="local_dev_executor",
            role="developer_support",
            capabilities=["repo_inspection", "file_workflows", "git_context", "local_triage"],
            health="healthy",
            supported_task_types=["developer_support", "general_local_assistance"],
            execution_mode="local_supervised",
            result_contract=_result_contract(),
        ),
        ExecutorDefinition(
            id="openclaw_executor",
            role="build_execution",
            capabilities=["project_builds", "artifact_generation", "development_reports"],
            health="planned",
            supported_task_types=["project_build", "developer_support"],
            execution_mode="delegated_subsystem",
            result_contract=_result_contract(),
        ),
        ExecutorDefinition(
            id="wraith_executor",
            role="security_specialist",
            capabilities=["recon", "black_box_testing", "white_box_review", "campaign_automation"],
            health="planned",
            supported_task_types=["security_assessment", "security_review"],
            execution_mode="delegated_subsystem",
            result_contract=_result_contract(),
        ),
    ]


def get_executor_definition(executor_id: str) -> ExecutorDefinition:
    for executor in executor_registry():
        if executor.id == executor_id:
            return executor
    raise ValueError(f"Unknown executor '{executor_id}'")


def executor_registry_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": executor.id,
            "role": executor.role,
            "capabilities": executor.capabilities,
            "health": executor.health,
            "supported_task_types": executor.supported_task_types,
            "execution_mode": executor.execution_mode,
            "result_contract": executor.result_contract,
        }
        for executor in executor_registry()
    ]


async def execute_executor(executor_id: str, task: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    executor = get_executor_definition(executor_id)
    summary = _executor_summary(executor, task, step)
    return {
        "status": "ok",
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "artifacts": {
            "executor_id": executor.id,
            "role": executor.role,
            "task_class": task["task_class"],
            "step": step["title"],
        },
        "user_message": summary,
    }


def _executor_summary(executor: ExecutorDefinition, task: dict[str, Any], step: dict[str, Any]) -> str:
    if executor.id == "openclaw_executor":
        return f"OpenClaw accepted {task['task_class']} work for step '{step['title']}' and reported a structured build/project summary back to Oxy."
    if executor.id == "wraith_executor":
        return f"Wraith accepted {task['task_class']} work for step '{step['title']}' and reported a structured security summary back to Oxy."
    if executor.id == "local_device_executor":
        return f"Oxy completed supervised device-support work for '{step['title']}'."
    return f"Oxy completed supervised developer-support work for '{step['title']}'."


def _result_contract() -> dict[str, Any]:
    return {
        "status": "ok|failed",
        "artifacts": {},
        "user_message": "text",
    }
