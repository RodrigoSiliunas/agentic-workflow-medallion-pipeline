"""Pipeline Editor routes — sessões, drafts, preview, export, PR e share."""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.database.session import get_db
from app.models.audit import AuditLog
from app.models.pipeline import Pipeline
from app.models.pipeline_editor import (
    PipelineEditArtifact,
    PipelineEditMessage,
    PipelineEditSession,
    PipelineEditVersion,
    PipelineShare,
)
from app.models.template import Template
from app.schemas.pipeline_editor import (
    ApproveRequest,
    CreateEditSessionRequest,
    DraftUpdateRequest,
    EditMessageRequest,
    EditMessageResponse,
    EditSessionResponse,
    EditVersionResponse,
    ExportRequest,
    PreviewRequest,
    RevertRequest,
    ShareRequest,
)
from app.services.databricks_service import DatabricksService
from app.services.github_service import GitHubService
from app.services.pipeline_editor.artifacts import build_prompt_markdown
from app.services.pipeline_editor.downstream_impact import check_downstream_impact
from app.services.pipeline_editor.manifest import (
    DEFAULT_CATALOG,
    ensure_silver_node,
    load_manifest_for_template,
    manifest_for_editor,
)
from app.services.pipeline_editor.nl_agent import build_edit_proposal_from_nl
from app.services.pipeline_editor.preview import (
    PreviewExportError,
    build_export_result,
    export_preview_rows,
    preview_rows_for_export,
    run_preview,
)
from app.services.pipeline_editor.preview_sql import PreviewSqlError, validate_target_table
from app.services.pipeline_editor.schemas import TransformDraft
from app.services.pipeline_editor.secure_pr import build_code_diff, validate_generated_files

logger = structlog.get_logger()

router = APIRouter()
share_router = APIRouter()


async def _load_pipeline(
    db: AsyncSession,
    auth: AuthContext,
    pipeline_id: uuid.UUID,
) -> Pipeline:
    result = await db.execute(
        select(Pipeline).where(
            Pipeline.id == pipeline_id,
            Pipeline.company_id == auth.company_id,
        )
    )
    pipeline = result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline nao encontrado")
    return pipeline


async def _load_session(
    db: AsyncSession,
    auth: AuthContext,
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
) -> PipelineEditSession:
    result = await db.execute(
        select(PipelineEditSession).where(
            PipelineEditSession.id == session_id,
            PipelineEditSession.pipeline_id == pipeline_id,
            PipelineEditSession.company_id == auth.company_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sessao de edicao nao encontrada")
    return session


def _template_slug(pipeline: Pipeline) -> str:
    config = pipeline.config or {}
    return str(
        config.get("template_slug")
        or config.get("template")
        or "pipeline-seguradora-whatsapp"
    )


def _pipeline_catalog(pipeline: Pipeline) -> str:
    """Catalog Unity efetivo do pipeline.

    O saga de deploy persiste em `config["catalog"]` o catalog que de fato
    provisionou (prod=`medallion`, dev=`medallion_dev`, ou custom do wizard).
    Fallback em `env_vars.catalog` e, por fim, no default — assim pipelines
    antigos (seed) sem o campo continuam apontando pra `medallion`.
    """
    config = pipeline.config or {}
    return str(
        config.get("catalog")
        or (config.get("env_vars") or {}).get("catalog")
        or DEFAULT_CATALOG
    )


async def _resolve_manifest(db: AsyncSession, pipeline: Pipeline):
    slug = _template_slug(pipeline)
    config = pipeline.config or {}
    template_name: str | None = None
    result = await db.execute(select(Template).where(Template.slug == slug))
    template = result.scalar_one_or_none()
    if template:
        template_name = template.name
    return load_manifest_for_template(
        slug,
        template_name=template_name,
        config_manifest=config.get("manifest"),
        catalog=_pipeline_catalog(pipeline),
    )


async def _current_version(
    db: AsyncSession,
    auth: AuthContext,
    session: PipelineEditSession,
) -> PipelineEditVersion:
    if not session.current_version_id:
        raise HTTPException(status_code=404, detail="Sessao ainda nao possui draft")
    result = await db.execute(
        select(PipelineEditVersion).where(
            PipelineEditVersion.id == session.current_version_id,
            PipelineEditVersion.company_id == auth.company_id,
            PipelineEditVersion.session_id == session.id,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Versao atual nao encontrada")
    return version


async def _create_version(
    db: AsyncSession,
    auth: AuthContext,
    session: PipelineEditSession,
    draft: TransformDraft,
    *,
    generated_files: dict | None = None,
    validation_result: dict | None = None,
    preview_result: dict | None = None,
    pr_metadata: dict | None = None,
) -> PipelineEditVersion:
    existing = await db.execute(
        select(PipelineEditVersion).where(
            PipelineEditVersion.session_id == session.id,
            PipelineEditVersion.company_id == auth.company_id,
        )
    )
    version = PipelineEditVersion(
        company_id=auth.company_id,
        pipeline_id=session.pipeline_id,
        session_id=session.id,
        version_number=len(existing.scalars().all()) + 1,
        draft=draft.model_dump(mode="json"),
        generated_files=generated_files or {},
        validation_result=validation_result or {},
        preview_result=preview_result or {},
        pr_metadata=pr_metadata or {},
    )
    db.add(version)
    await db.flush()
    session.current_version_id = version.id
    return version


def _version_to_draft(version: PipelineEditVersion) -> TransformDraft:
    return TransformDraft.model_validate(version.draft)


def _validate_silver_draft(draft: TransformDraft, manifest):
    try:
        node = ensure_silver_node(manifest, draft.target_node)
        # Cross-check do target_table contra as output_tables declaradas no node
        # do manifest — impede preview/export de tabelas arbitrarias (cross-tenant).
        validate_target_table(draft.target_table, node.output_tables)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (ValueError, PreviewSqlError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return node


@router.get("/{pipeline_id}", response_model=dict)
async def get_pipeline_workspace(
    pipeline_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_db),
):
    pipeline = await _load_pipeline(db, auth, pipeline_id)
    manifest = manifest_for_editor(await _resolve_manifest(db, pipeline))
    return {
        "id": str(pipeline.id),
        "name": pipeline.name,
        "description": pipeline.description,
        "databricks_job_id": pipeline.databricks_job_id,
        "github_repo": pipeline.github_repo,
        "config": pipeline.config or {},
        "manifest": manifest.model_dump(mode="json"),
        "editor_scope": {
            "layers": ["silver"],
            "message": "Pipeline Editor disponivel apenas para camada Silver.",
        },
    }


@router.get("/{pipeline_id}/edit-sessions", response_model=list[EditSessionResponse])
async def list_edit_sessions(
    pipeline_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_db),
):
    await _load_pipeline(db, auth, pipeline_id)
    result = await db.execute(
        select(PipelineEditSession)
        .where(
            PipelineEditSession.company_id == auth.company_id,
            PipelineEditSession.pipeline_id == pipeline_id,
        )
        .order_by(PipelineEditSession.updated_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/{pipeline_id}/edit-sessions",
    response_model=EditSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_edit_session(
    pipeline_id: uuid.UUID,
    data: CreateEditSessionRequest,
    auth: AuthContext = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_db),
):
    pipeline = await _load_pipeline(db, auth, pipeline_id)
    session = PipelineEditSession(
        company_id=auth.company_id,
        pipeline_id=pipeline.id,
        created_by_user_id=auth.user_id,
        title=data.title or f"Edicao {pipeline.name}",
        target_layers=data.target_layers,
        base_ref=data.base_ref,
        status="draft",
    )
    db.add(session)
    await db.flush()
    return session


@router.post(
    "/{pipeline_id}/edit-sessions/{session_id}/messages",
    response_model=EditMessageResponse,
)
async def send_editor_message(
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    data: EditMessageRequest,
    auth: AuthContext = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_db),
):
    pipeline = await _load_pipeline(db, auth, pipeline_id)
    session = await _load_session(db, auth, pipeline_id, session_id)
    manifest = await _resolve_manifest(db, pipeline)
    if data.draft is not None:
        _validate_silver_draft(data.draft, manifest)
    proposal = await build_edit_proposal_from_nl(
        db=db,
        company_id=auth.company_id,
        user_message=data.message,
        draft=data.draft,
        manifest=manifest,
    )
    user_message = PipelineEditMessage(
        company_id=auth.company_id,
        pipeline_id=pipeline.id,
        session_id=session.id,
        role="user",
        content=data.message,
        structured_state={},
    )
    assistant_message = PipelineEditMessage(
        company_id=auth.company_id,
        pipeline_id=pipeline.id,
        session_id=session.id,
        role="assistant",
        content=proposal.explanation,
        structured_state=proposal.model_dump(mode="json"),
    )
    db.add_all([user_message, assistant_message])
    version = await _create_version(db, auth, session, proposal.draft)
    return EditMessageResponse(
        session_id=session.id,
        message=proposal.explanation,
        proposal=proposal,
        version_id=version.id,
    )


@router.put(
    "/{pipeline_id}/edit-sessions/{session_id}/draft",
    response_model=EditVersionResponse,
)
async def update_draft(
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    data: DraftUpdateRequest,
    auth: AuthContext = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_db),
):
    pipeline = await _load_pipeline(db, auth, pipeline_id)
    session = await _load_session(db, auth, pipeline_id, session_id)
    manifest = await _resolve_manifest(db, pipeline)
    _validate_silver_draft(data.draft, manifest)
    version = await _create_version(db, auth, session, data.draft)
    return version


@router.post("/{pipeline_id}/edit-sessions/{session_id}/preview", response_model=dict)
async def create_preview(
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    data: PreviewRequest,
    auth: AuthContext = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_db),
):
    pipeline = await _load_pipeline(db, auth, pipeline_id)
    session = await _load_session(db, auth, pipeline_id, session_id)
    version = await _current_version(db, auth, session)
    draft = _version_to_draft(version)
    manifest = await _resolve_manifest(db, pipeline)
    node = _validate_silver_draft(draft, manifest)
    databricks = DatabricksService(db, auth.company_id)
    preview = await run_preview(
        databricks,
        company_id=auth.company_id,
        pipeline_id=pipeline_id,
        session_id=session_id,
        draft=draft,
        sample_rows=data.sample_rows,
        output_tables=node.output_tables,
    )
    version.preview_result = preview
    if preview.get("status") != "ready":
        logger.warning(
            "pipeline_editor_preview_not_ready",
            pipeline_id=str(pipeline_id),
            session_id=str(session_id),
            status=preview.get("status"),
            error=preview.get("error"),
        )
    db.add(
        PipelineEditArtifact(
            company_id=auth.company_id,
            pipeline_id=pipeline_id,
            session_id=session_id,
            version_id=version.id,
            artifact_type="preview",
            name="preview.json",
            content=preview,
        )
    )
    await db.flush()
    return preview


@router.post("/{pipeline_id}/edit-sessions/{session_id}/export", response_model=dict)
async def export_preview(
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    data: ExportRequest,
    auth: AuthContext = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_db),
):
    pipeline = await _load_pipeline(db, auth, pipeline_id)
    session = await _load_session(db, auth, pipeline_id, session_id)
    version = await _current_version(db, auth, session)
    draft = _version_to_draft(version)
    manifest = await _resolve_manifest(db, pipeline)
    node = _validate_silver_draft(draft, manifest)
    try:
        export = build_export_result(
            company_id=auth.company_id,
            pipeline_id=pipeline_id,
            session_id=session_id,
            export_format=data.format,
            preview_result=version.preview_result,
            output_tables=node.output_tables,
        )
    except PreviewExportError as exc:
        logger.warning(
            "pipeline_editor_export_failed",
            pipeline_id=str(pipeline_id),
            session_id=str(session_id),
            format=data.format,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.add(
        PipelineEditArtifact(
            company_id=auth.company_id,
            pipeline_id=pipeline_id,
            session_id=session_id,
            version_id=version.id,
            artifact_type=f"export:{data.format}",
            name=f"preview.{data.format}",
            content=export,
            storage_uri=export["download_url"],
        )
    )
    db.add(
        AuditLog(
            company_id=auth.company_id,
            user_id=auth.user_id,
            action="pipeline_editor_export",
            details=str(
                {
                    "pipeline_id": str(pipeline_id),
                    "session_id": str(session_id),
                    "format": data.format,
                    "row_count": export.get("row_count", 0),
                }
            ),
            channel="web",
        )
    )
    await db.flush()
    return export


@router.get("/{pipeline_id}/edit-sessions/{session_id}/exports/latest.{export_format}")
async def download_export(
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    export_format: str,
    auth: AuthContext = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_db),
):
    if export_format not in {"csv", "parquet"}:
        raise HTTPException(status_code=400, detail="Formato de exportacao invalido")

    await _load_pipeline(db, auth, pipeline_id)
    session = await _load_session(db, auth, pipeline_id, session_id)
    version = await _current_version(db, auth, session)
    try:
        rows = preview_rows_for_export(version.preview_result)
        payload, media_type = export_preview_rows(rows, export_format)
    except PreviewExportError as exc:
        logger.warning(
            "pipeline_editor_export_download_failed",
            pipeline_id=str(pipeline_id),
            session_id=str(session_id),
            format=export_format,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    filename = f"preview_{session_id.hex[:8]}.{export_format}"
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{pipeline_id}/edit-sessions/{session_id}/prompt.md", response_model=dict)
async def get_prompt_markdown(
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_db),
):
    pipeline = await _load_pipeline(db, auth, pipeline_id)
    session = await _load_session(db, auth, pipeline_id, session_id)
    version = await _current_version(db, auth, session)
    markdown = build_prompt_markdown(
        session_id=session.id,
        pipeline_name=pipeline.name,
        user_request=session.title,
        draft=_version_to_draft(version),
        validation=version.validation_result,
        preview=version.preview_result,
    )
    return {"filename": "prompt.md", "content": markdown}


@router.post("/{pipeline_id}/edit-sessions/{session_id}/share", response_model=dict)
async def share_edit_session(
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    data: ShareRequest,
    auth: AuthContext = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_db),
):
    await _load_pipeline(db, auth, pipeline_id)
    session = await _load_session(db, auth, pipeline_id, session_id)
    token = secrets.token_urlsafe(32)
    share = PipelineShare(
        company_id=auth.company_id,
        pipeline_id=pipeline_id,
        session_id=data.session_id or session.id,
        artifact_id=data.artifact_id,
        created_by_user_id=auth.user_id,
        share_token=token,
        role=data.role,
        expires_at=data.expires_at,
        is_active=True,
    )
    db.add(share)
    await db.flush()
    db.add(
        AuditLog(
            company_id=auth.company_id,
            user_id=auth.user_id,
            action="pipeline_editor_share_created",
            details=str({"pipeline_id": str(pipeline_id), "session_id": str(session_id)}),
            channel="web",
        )
    )
    await db.flush()
    return {"share_token": token, "url": f"/shared/pipeline-edit/{token}"}


async def _load_downstream_notebooks(
    github: GitHubService,
    paths: list[str],
    ref: str,
) -> dict[str, str]:
    """Lê notebooks downstream em paralelo via GitHub, ignorando arquivos ausentes."""
    async def _safe_read(path: str) -> tuple[str, str | None]:
        try:
            content = await github.read_file(path, ref)
            return path, content
        except Exception:
            logger.warning("downstream_notebook_not_found", path=path, ref=ref)
            return path, None

    results = await asyncio.gather(*[_safe_read(p) for p in paths])
    return {path: content for path, content in results if content is not None}


@router.post("/{pipeline_id}/edit-sessions/{session_id}/approve", response_model=dict)
async def approve_edit_version(
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    data: ApproveRequest,
    auth: AuthContext = Depends(require_permission("create_pr")),
    db: AsyncSession = Depends(get_db),
):
    pipeline = await _load_pipeline(db, auth, pipeline_id)
    session = await _load_session(db, auth, pipeline_id, session_id)
    version = await _current_version(db, auth, session)
    preview = version.preview_result or {}
    if preview.get("status") != "ready":
        db.add(
            AuditLog(
                company_id=auth.company_id,
                user_id=auth.user_id,
                action="pipeline_editor_approve_blocked",
                details=str(
                    {
                        "pipeline_id": str(pipeline_id),
                        "session_id": str(session_id),
                        "preview_status": preview.get("status"),
                    }
                ),
                channel="web",
            )
        )
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Preview obrigatorio antes de aprovar. "
                "Execute o preview e aguarde status ready."
            ),
        )

    draft = _version_to_draft(version)
    manifest = await _resolve_manifest(db, pipeline)
    node = manifest.resolve_node(draft.target_node)
    github = GitHubService(db, auth.company_id)

    # Guard de impacto downstream: lê notebooks gold/validation em paralelo e bloqueia
    # approve se drop_column/rename_column afetar colunas referenciadas downstream.
    if manifest.downstream_scan_paths and not data.force_downstream:
        ref = session.base_ref or "dev"
        notebook_sources = await _load_downstream_notebooks(
            github, manifest.downstream_scan_paths, ref
        )
        impact = check_downstream_impact(draft, notebook_sources)
        if impact["blocked"]:
            version.validation_result = {
                "valid": False, "checks": [], "errors": [], "downstream_impact": impact
            }
            await db.flush()
            return {
                "status": "downstream_blocked",
                "downstream_impact": impact,
            }

    source = await github.read_file(node.file_path, session.base_ref or "dev")
    source_by_path = {node.file_path: source}
    files, validation = validate_generated_files(
        source_by_path=source_by_path,
        draft=draft,
        manifest=manifest,
    )
    diff = build_code_diff(source_by_path=source_by_path, generated_files=files)
    version.generated_files = files
    version.validation_result = validation
    if not validation["valid"]:
        await db.flush()
        return {"status": "validation_failed", "validation": validation, "diff": diff}
    pr_metadata = {"status": "validated"}
    if data.create_pr:
        pr_metadata = await github.create_pr(
            title=f"Pipeline edit: {session.title}",
            body="PR gerado pelo Pipeline Editor apos preview e aprovacao humana.",
            branch=f"pipeline-editor/{session.id.hex[:8]}",
            files=files,
        )
    version.pr_metadata = pr_metadata
    session.status = "pr_created" if data.create_pr else "validated"
    db.add(
        AuditLog(
            company_id=auth.company_id,
            user_id=auth.user_id,
            action="pipeline_editor_approved",
            details=str({"pipeline_id": pipeline_id, "session_id": session_id}),
            channel="web",
        )
    )
    await db.flush()
    return {
        "status": session.status,
        "validation": validation,
        "pr": pr_metadata,
        "diff": diff,
    }


@router.post("/{pipeline_id}/edit-sessions/{session_id}/revert", response_model=dict)
async def revert_edit_session(
    pipeline_id: uuid.UUID,
    session_id: uuid.UUID,
    data: RevertRequest,
    auth: AuthContext = Depends(require_permission("create_pr")),
    db: AsyncSession = Depends(get_db),
):
    await _load_pipeline(db, auth, pipeline_id)
    session = await _load_session(db, auth, pipeline_id, session_id)
    if data.mode == "draft" and data.version_id:
        await _current_version(db, auth, session)
        session.current_version_id = data.version_id
        session.status = "draft"
        await db.flush()
        return {"status": "draft_reverted", "current_version_id": str(data.version_id)}

    if data.mode in {"revert_pr", "close_pr"}:
        version = await _current_version(db, auth, session)
        pr_metadata = version.pr_metadata or {}
        pr_result: dict | None = None
        pr_number = pr_metadata.get("pr_number")
        if pr_number:
            github = GitHubService(db, auth.company_id)
            try:
                pr_result = await github.close_pull_request(int(pr_number))
            except Exception as exc:
                logger.warning(
                    "pipeline_editor_revert_pr_failed",
                    pipeline_id=str(pipeline_id),
                    session_id=str(session_id),
                    pr_number=pr_number,
                    error=str(exc),
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Falha ao fechar PR #{pr_number}: {exc}",
                ) from exc
        if data.version_id:
            session.current_version_id = data.version_id
        session.status = "draft"
        db.add(
            AuditLog(
                company_id=auth.company_id,
                user_id=auth.user_id,
                action="pipeline_editor_pr_reverted",
                details=str(
                    {
                        "pipeline_id": str(pipeline_id),
                        "session_id": str(session_id),
                        "pr_number": pr_number,
                    }
                ),
                channel="web",
            )
        )
        await db.flush()
        current_version_id = (
            str(session.current_version_id) if session.current_version_id else None
        )
        return {
            "status": "pr_reverted",
            "current_version_id": current_version_id,
            "pr": pr_result,
        }

    if data.mode == "restore_table":
        version = await _current_version(db, auth, session)
        table = data.table or (version.draft or {}).get("target_table")
        if not table:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="table obrigatorio para mode=restore_table",
            )

        databricks = DatabricksService(db, auth.company_id)
        restore_result: dict | None = None
        revert_pr_result: dict | None = None

        try:
            delta_version = data.delta_version
            if delta_version is None:
                history = await databricks.get_table_history(table, limit=2)
                if len(history) >= 2:
                    raw_version = history[1].get("version")
                    delta_version = int(raw_version) if raw_version is not None else None

            if delta_version is not None:
                restore_result = await databricks.restore_table(table, version=delta_version)
            else:
                restore_result = {"status": "skipped", "reason": "sem versao anterior no historico"}
        except Exception as exc:
            logger.warning(
                "pipeline_editor_restore_table_failed",
                pipeline_id=str(pipeline_id),
                session_id=str(session_id),
                table=table,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao restaurar tabela {table}: {exc}",
            ) from exc

        if data.revert_notebook_pr:
            pr_metadata = version.pr_metadata or {}
            pr_number = pr_metadata.get("pr_number")
            if pr_number:
                github = GitHubService(db, auth.company_id)
                try:
                    revert_pr_result = await github.revert_merged_pr(int(pr_number))
                except Exception as exc:
                    logger.warning(
                        "pipeline_editor_revert_notebook_pr_failed",
                        pipeline_id=str(pipeline_id),
                        pr_number=pr_number,
                        error=str(exc),
                    )
                    revert_pr_result = {"status": "failed", "error": str(exc)}

        if data.version_id:
            session.current_version_id = data.version_id
        session.status = "draft"
        db.add(
            AuditLog(
                company_id=auth.company_id,
                user_id=auth.user_id,
                action="pipeline_editor_table_restored",
                details=str(
                    {
                        "pipeline_id": str(pipeline_id),
                        "session_id": str(session_id),
                        "table": table,
                        "delta_version": delta_version,
                    }
                ),
                channel="web",
            )
        )
        await db.flush()
        return {
            "status": "table_restored",
            "table": table,
            "delta_version": delta_version,
            "restore": restore_result,
            "revert_pr": revert_pr_result,
            "current_version_id": (
                str(session.current_version_id) if session.current_version_id else None
            ),
        }

    session.status = f"{data.mode}_requested"
    await db.flush()
    return {"status": session.status}


async def _load_active_share(db: AsyncSession, token: str) -> PipelineShare:
    result = await db.execute(
        select(PipelineShare).where(
            PipelineShare.share_token == token,
            PipelineShare.is_active.is_(True),
        )
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Link de compartilhamento invalido ou inativo")
    if share.expires_at and share.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Link de compartilhamento expirado")
    return share


@share_router.get("/pipeline-edit/{token}")
async def get_shared_pipeline_edit(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Resolve token de share para visualizacao read-only (sem edicao/aprovacao)."""
    share = await _load_active_share(db, token)
    pipeline_result = await db.execute(select(Pipeline).where(Pipeline.id == share.pipeline_id))
    pipeline = pipeline_result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline nao encontrado")

    session: PipelineEditSession | None = None
    version: PipelineEditVersion | None = None
    if share.session_id:
        session_result = await db.execute(
            select(PipelineEditSession).where(PipelineEditSession.id == share.session_id)
        )
        session = session_result.scalar_one_or_none()
        if session and session.current_version_id:
            version_result = await db.execute(
                select(PipelineEditVersion).where(
                    PipelineEditVersion.id == session.current_version_id
                )
            )
            version = version_result.scalar_one_or_none()

    manifest = manifest_for_editor(await _resolve_manifest(db, pipeline))
    prompt_markdown = None
    preview = None
    draft = None
    if session and version:
        draft = _version_to_draft(version)
        preview = version.preview_result or {}
        prompt_markdown = build_prompt_markdown(
            session_id=session.id,
            pipeline_name=pipeline.name,
            user_request=session.title,
            draft=draft,
            validation=version.validation_result,
            preview=preview,
        )

    db.add(
        AuditLog(
            company_id=share.company_id,
            user_id=share.created_by_user_id,
            action="pipeline_editor_share_viewed",
            details=str({"share_token": token[:8], "pipeline_id": str(share.pipeline_id)}),
            channel="share",
        )
    )
    await db.flush()

    return {
        "role": share.role,
        "pipeline": {
            "id": str(pipeline.id),
            "name": pipeline.name,
            "description": pipeline.description,
        },
        "session": {
            "id": str(session.id) if session else None,
            "title": session.title if session else None,
            "status": session.status if session else None,
        },
        "manifest": manifest.model_dump(mode="json"),
        "draft": draft.model_dump(mode="json") if draft else None,
        "preview": preview,
        "prompt_markdown": prompt_markdown,
        "read_only": True,
    }
