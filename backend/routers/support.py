from fastapi import APIRouter, HTTPException

from services.support_daemon import escalate_support_incident, run_support_fix, support_daemon_status

router = APIRouter()


@router.get("/support/status")
async def support_status():
    return await support_daemon_status()


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
