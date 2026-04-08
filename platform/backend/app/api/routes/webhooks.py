"""Webhook routes — stub, implementado na Phase 5."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/omni")
async def webhook_omni():
    return {"message": "TODO: Phase 5"}


@router.post("/pipeline")
async def webhook_pipeline():
    return {"message": "TODO: Phase 5"}
