"""Templates routes — marketplace de templates para one-click deploy."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user
from app.database.session import get_db
from app.models.template import Template
from app.schemas.template import TemplateResponse

router = APIRouter()


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    category: str | None = Query(None, description="Filtrar por categoria"),
    search: str | None = Query(None, description="Busca em nome/tagline/tags"),
    published_only: bool = Query(True),
    _auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista templates publicados com filtros opcionais."""
    query = select(Template).order_by(Template.name)
    if published_only:
        query = query.where(Template.published.is_(True))
    if category:
        query = query.where(Template.category == category)
    if search:
        like = f"%{search.lower()}%"
        query = query.where(
            or_(
                Template.name.ilike(like),
                Template.tagline.ilike(like),
                Template.description.ilike(like),
            )
        )

    result = await db.execute(query)
    templates = result.scalars().all()
    return [_serialize(t) for t in templates]


@router.get("/{slug}", response_model=TemplateResponse)
async def get_template(
    slug: str,
    _auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna um template pelo slug."""
    result = await db.execute(select(Template).where(Template.slug == slug))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template nao encontrado",
        )
    return _serialize(template)


def _serialize(template: Template) -> dict:
    return {
        "id": str(template.id),
        "slug": template.slug,
        "name": template.name,
        "tagline": template.tagline,
        "description": template.description,
        "category": template.category,
        "tags": template.tags or [],
        "icon": template.icon,
        "icon_bg": template.icon_bg,
        "version": template.version,
        "author": template.author,
        "deploy_count": template.deploy_count,
        "duration_estimate": template.duration_estimate,
        "architecture_bullets": template.architecture_bullets or [],
        "env_schema": template.env_schema or [],
        "changelog": template.changelog or [],
        "published": template.published,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }
