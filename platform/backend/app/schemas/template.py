"""Pydantic schemas para templates do marketplace."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    tagline: str
    description: str
    category: str
    tags: list[str]
    icon: str
    icon_bg: str
    version: str
    author: str
    deploy_count: int
    duration_estimate: str
    architecture_bullets: list[str]
    env_schema: list[dict]
    changelog: list[dict]
    published: bool
    created_at: datetime
    updated_at: datetime
