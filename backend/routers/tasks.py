from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.orchestrator import create_task, get_task, list_tasks, resolve_approval, retry_step
from services.tool_registry import registry_payload

router = APIRouter()


class CreateTaskRequest(BaseModel):
    prompt: str
    conversation_id: Optional[str] = None


class ResolveApprovalRequest(BaseModel):
    approved: bool


@router.get("/tasks")
async def tasks_index():
    return {"tasks": await list_tasks()}


@router.post("/tasks/plan")
async def tasks_plan(body: CreateTaskRequest):
    try:
        return await create_task(body.prompt, body.conversation_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tasks/{task_id}")
async def tasks_show(task_id: str):
    try:
        return await get_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/approvals/{approval_id}")
async def tasks_approve(task_id: str, approval_id: str, body: ResolveApprovalRequest):
    try:
        return await resolve_approval(task_id, approval_id, body.approved)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/steps/{step_id}/retry")
async def tasks_retry(task_id: str, step_id: str):
    try:
        return await retry_step(task_id, step_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tools")
async def tools_index():
    return {"tools": registry_payload()}
