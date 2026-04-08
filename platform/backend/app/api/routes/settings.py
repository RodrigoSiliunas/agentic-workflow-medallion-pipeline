"""Settings routes — stub, implementado na Phase 2."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/credentials")
async def list_credentials():
    return {"message": "TODO: Phase 2"}
