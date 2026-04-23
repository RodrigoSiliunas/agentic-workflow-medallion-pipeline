"""Chat routes — SSE streaming + thread management."""

import json
import uuid

import structlog
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

logger = structlog.get_logger()

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

    # Filtro de intencao — rejeita perguntas off-topic ANTES de gastar
    # tokens com o LLM. Resposta local instantanea, custo zero.
    off_topic = _check_off_topic(data.message)
    if off_topic:
        user_msg = Message(
            thread_id=thread.id, role="user", content=data.message, channel="web"
        )
        db.add(user_msg)
        assistant_msg = Message(
            thread_id=thread.id, role="assistant", content=off_topic, channel="web"
        )
        db.add(assistant_msg)
        if not thread.title:
            thread.title = data.message[:100]
        await db.commit()

        async def _off_topic_stream():
            yield f"data: {json.dumps({'type': 'token', 'content': off_topic})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'model': 'local', 'tokens': 0})}\n\n"

        return StreamingResponse(
            _off_topic_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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

    orchestrator_model = "unknown"

    async def event_stream():
        nonlocal orchestrator_model
        full_response = ""
        actions = []

        try:
            async for event in orchestrator.process_message(
                user_message=data.message,
                pipeline_job_id=job_id,
                conversation_history=conversation_history[:-1],
                model_override=data.model,
                provider_override=getattr(data, "provider", None),
            ):
                if event["type"] == "token":
                    full_response += event["content"]
                elif event["type"] == "action":
                    actions.append(event)
                elif event["type"] == "done":
                    orchestrator_model = event.get("model", "unknown")

                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.exception("chat stream error", thread_id=str(thread.id))
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            full_response = f"Erro: {e}"

        # Persistir resposta do assistente no DB pra que sobreviva refresh.
        # Usa nova session porque a session do request pode ja ter fechado.
        if full_response:
            try:
                from app.database.session import AsyncSessionLocal

                async with AsyncSessionLocal() as save_db:
                    assistant_msg = Message(
                        thread_id=thread.id,
                        role="assistant",
                        content=full_response,
                        channel="web",
                        actions=actions if actions else None,
                        model=orchestrator_model,
                    )
                    save_db.add(assistant_msg)
                    await save_db.commit()
            except Exception as save_err:
                logger.error("Failed to save assistant msg", error=str(save_err))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Filtro de intencao — rejeita off-topic sem gastar tokens LLM
# ---------------------------------------------------------------------------
_PIPELINE_KEYWORDS = {
    "pipeline", "bronze", "silver", "gold", "etl", "medallion", "databricks",
    "delta", "spark", "notebook", "job", "run", "task", "workflow", "observer",
    "agente", "agent", "falha", "erro", "error", "fail", "status", "log",
    "deploy", "schema", "tabela", "table", "coluna", "column", "query", "sql",
    "s3", "bucket", "parquet", "ingestion", "ingest", "dedup", "validation",
    "check", "quality", "pr", "pull request", "github", "fix", "diagnos",
    "custo", "cost", "token", "claude", "anthropic", "llm", "modelo",
    "secret", "credential", "catalog", "warehouse", "cluster",
    "whatsapp", "seguro", "seguradora", "conversa", "mensagem",
    "mascaramento", "pii", "hmac", "cpf", "telefone", "email",
    "sentiment", "funnel", "nps", "churn", "lead", "persona",
    "schedule", "cron", "trigger", "chaos", "rollback", "overwrite",
    "metric", "metrica", "dashboard", "observability", "monitor",
    # Temporal / follow-up (usuario perguntando sobre resultado anterior)
    "data", "quando", "hora", "ultimo", "ultima", "executou", "rodou",
    "sucesso", "success", "resultado", "duracao", "correcao", "correção",
    # Codigo / mudancas
    "codigo", "código", "mudou", "alterou", "alteracao", "commit",
    "arquivo", "diff", "patch", "branch", "merge",
}

_OFF_TOPIC_RESPONSE = (
    "Essa pergunta esta fora do escopo do que posso ajudar. "
    "Sou o assistente do seu pipeline Medallion — posso:\n\n"
    "- Verificar **status** e **logs** de execucoes\n"
    "- Consultar **tabelas** Delta (SELECT)\n"
    "- Analisar **erros** e diagnosticar falhas\n"
    "- Listar **PRs** do Observer Agent\n"
    "- Verificar **schemas** e **metricas**\n"
    "- Disparar runs ou criar PRs\n\n"
    "Pergunte algo sobre o pipeline e terei prazer em ajudar!"
)


def _check_off_topic(message: str) -> str | None:
    """Retorna resposta local se a mensagem e off-topic, None se on-topic.

    Heuristica simples: se a mensagem nao contem nenhuma keyword relacionada
    ao pipeline E tem menos de 15 palavras (perguntas curtas genericas como
    "que dia e hoje", "tudo bem"), retorna resposta padrao.

    Mensagens longas (>15 palavras) sao passadas pro LLM mesmo sem keywords
    porque podem ter contexto implicito.
    """
    words = message.lower().split()

    # Saudacoes curtas — responde localmente
    greetings = {"oi", "ola", "hey", "hi", "hello", "e ai", "fala", "bom dia", "boa tarde"}
    if len(words) <= 3 and any(g in message.lower() for g in greetings):
        return (
            "Ola! Sou o assistente do seu pipeline Medallion. "
            "Como posso ajudar? Pergunte sobre status, logs, erros, "
            "tabelas ou qualquer aspecto do pipeline."
        )

    # Mensagens longas — sempre passa pro LLM (pode ter contexto implicito)
    if len(words) > 15:
        return None

    # Checa se alguma keyword do pipeline esta presente
    msg_lower = message.lower()
    for kw in _PIPELINE_KEYWORDS:
        if kw in msg_lower:
            return None  # On-topic — passa pro LLM

    # Nenhuma keyword encontrada em mensagem curta — off-topic
    return _OFF_TOPIC_RESPONSE
