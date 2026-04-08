"""Chat routes — SSE streaming + thread management."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user
from app.database.session import get_db
from app.models.chat import Message, Thread
from app.models.pipeline import Pipeline
from app.schemas.chat import (
    CreateThreadRequest,
    MessageResponse,
    SendMessageRequest,
    ThreadResponse,
)
from app.services.llm_orchestrator import LLMOrchestrator

router = APIRouter()


@router.get("/threads", response_model=list[ThreadResponse])
async def list_threads(
    pipeline_id: uuid.UUID | None = None,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista threads do usuario (opcionalmente filtrado por pipeline)."""
    query = select(Thread).where(
        Thread.user_id == auth.user_id
    ).order_by(Thread.updated_at.desc())

    if pipeline_id:
        query = query.where(Thread.pipeline_id == pipeline_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/threads", response_model=ThreadResponse, status_code=201)
async def create_thread(
    data: CreateThreadRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cria novo thread para um pipeline."""
    # Verificar que o pipeline pertence a empresa
    pipeline = await db.execute(
        select(Pipeline).where(
            Pipeline.id == uuid.UUID(data.pipeline_id),
            Pipeline.company_id == auth.company_id,
        )
    )
    if not pipeline.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline nao encontrado",
        )

    thread = Thread(
        pipeline_id=uuid.UUID(data.pipeline_id),
        user_id=auth.user_id,
    )
    db.add(thread)
    await db.flush()
    return thread


@router.get("/threads/{thread_id}/messages", response_model=list[MessageResponse])
async def get_thread_messages(
    thread_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna mensagens de um thread (verifica ownership)."""
    thread = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.user_id == auth.user_id)
    )
    if not thread.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread nao encontrado"
        )

    result = await db.execute(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deleta um thread (soft delete)."""
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.user_id == auth.user_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread nao encontrado"
        )
    thread.is_active = False
    await db.flush()


@router.post("/message")
async def send_message(
    data: SendMessageRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Envia mensagem e retorna resposta do LLM via SSE streaming."""
    # Verificar thread ownership
    thread_result = await db.execute(
        select(Thread).where(
            Thread.id == uuid.UUID(data.thread_id), Thread.user_id == auth.user_id
        )
    )
    thread = thread_result.scalar_one_or_none()
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread nao encontrado"
        )

    # Obter pipeline para job_id
    pipeline_result = await db.execute(
        select(Pipeline).where(Pipeline.id == thread.pipeline_id)
    )
    pipeline = pipeline_result.scalar_one()
    job_id = data.pipeline_job_id or pipeline.databricks_job_id or 0

    # Salvar mensagem do usuario
    user_msg = Message(
        thread_id=thread.id,
        role="user",
        content=data.message,
        channel="web",
    )
    db.add(user_msg)
    await db.flush()

    # Atualizar titulo do thread (se primeiro msg)
    if not thread.title:
        thread.title = data.message[:100]
        await db.flush()

    # Carregar historico
    history_result = await db.execute(
        select(Message)
        .where(Message.thread_id == thread.id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    history_msgs = list(reversed(history_result.scalars().all()))

    conversation_history = [
        {"role": m.role, "content": m.content}
        for m in history_msgs
        if m.role in ("user", "assistant")
    ]

    # Stream response via SSE
    orchestrator = LLMOrchestrator(db, auth.company_id, auth.name)

    async def event_stream():
        full_response = ""
        actions = []

        try:
            async for event in orchestrator.process_message(
                user_message=data.message,
                pipeline_job_id=job_id,
                conversation_history=conversation_history[:-1],  # Exclui a msg atual
            ):
                if event["type"] == "token":
                    full_response += event["content"]
                elif event["type"] == "action":
                    actions.append(event)
                elif event["type"] == "done":
                    pass  # Stream finalizado

                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            full_response = f"Erro: {e}"

        # Salvar resposta do assistente (fora do stream, nova session)
        # TODO: mover para background task para nao bloquear SSE close

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
