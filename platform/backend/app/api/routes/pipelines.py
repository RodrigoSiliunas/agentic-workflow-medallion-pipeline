"""Pipeline routes — stub, implementado na Phase 3."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_pipelines():
    return {"message": "TODO: Phase 3"}
