from fastapi import APIRouter

from services.support_daemon import support_daemon_status

router = APIRouter()


@router.get("/support/status")
async def support_status():
    return await support_daemon_status()
