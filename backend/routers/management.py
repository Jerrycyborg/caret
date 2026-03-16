from fastapi import APIRouter
from services.management import management_status

router = APIRouter()


@router.get("/management/status")
def get_management_status():
    return management_status()
