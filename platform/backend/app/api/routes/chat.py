"""Chat routes — stub, implementado na Phase 4."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/threads")
async def list_threads():
    return {"message": "TODO: Phase 4"}
