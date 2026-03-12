import json
import aiosqlite
from fastapi import APIRouter, HTTPException

from database import get_db_path
from services.orchestrator import get_task
from services.support_daemon import escalate_support_incident, run_support_fix, support_daemon_status
from services.ticketing import TicketingError, create_support_ticket

router = APIRouter()


@router.get("/support/status")
async def support_status():
    return await support_daemon_status()


@router.get("/support/incidents/{task_id}")
async def support_incident_detail(task_id: str):
    try:
        detail = await get_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if detail["task"]["task_kind"] != "support_incident":
        raise HTTPException(status_code=400, detail="Task is not a support incident.")

    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT event_type, message, metadata_json, created_at
            FROM policy_events
            WHERE task_id = ?
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (task_id,),
        ) as cur:
            policy_events = [dict(row) for row in await cur.fetchall()]
    for event in policy_events:
        event["metadata_json"] = json.loads(event["metadata_json"] or "{}")

    return {
        **detail,
        "incident": {
            "decision_kind": detail["task"]["support_severity"],
            "decision_reason": detail["task"]["support_decision_reason"],
            "recommended_fixes": detail["task"]["support_recommended_fixes"],
            "detected_at": detail["task"]["support_detected_at"] or detail["task"]["created_at"],
            "last_decision_at": detail["task"]["support_last_decision_at"] or detail["task"]["updated_at"],
            "source_signal": detail["task"]["support_source_signal"],
        },
        "policy_events": policy_events,
    }


@router.post("/support/incidents/{task_id}/run-fix")
async def support_run_fix(task_id: str):
    if not await run_support_fix(task_id):
        raise HTTPException(status_code=400, detail="Safe auto-fix is not available for this incident.")
    return await support_daemon_status()


@router.post("/support/incidents/{task_id}/escalate")
async def support_escalate(task_id: str):
    if not await escalate_support_incident(task_id):
        raise HTTPException(status_code=400, detail="Could not escalate this incident.")
    return await support_daemon_status()


@router.post("/support/incidents/{task_id}/create-ticket")
async def support_create_ticket(task_id: str):
    try:
        detail = await support_incident_detail(task_id)
        ticket = await create_support_ticket(task_id, detail)
    except TicketingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ticket": ticket,
        "status": await support_daemon_status(),
        "detail": await support_incident_detail(task_id),
    }
