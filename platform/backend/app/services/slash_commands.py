"""Parser e handler de slash commands para canais externos."""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import ActiveSession
from app.models.chat import Thread
from app.models.pipeline import Pipeline
from app.services.databricks_service import DatabricksService

logger = structlog.get_logger()

COMMANDS = {
    "/resume": "switch_pipeline",
    "/pipelines": "list_pipelines",
    "/status": "quick_status",
    "/threads": "list_threads",
    "/new": "new_thread",
    "/model": "change_model",
    "/whoami": "who_am_i",
    "/help": "show_help",
}


def is_slash_command(message: str) -> bool:
    """Verifica se a mensagem e um slash command."""
    return any(message.strip().lower().startswith(cmd) for cmd in COMMANDS)


def parse_command(message: str) -> tuple[str, str]:
    """Parseia comando e argumentos."""
    parts = message.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return cmd, args


class SlashCommandHandler:
    def __init__(
        self, db: AsyncSession, user_id: uuid.UUID,
        company_id: uuid.UUID, channel: str,
    ):
        self.db = db
        self.user_id = user_id
        self.company_id = company_id
        self.channel = channel

    async def handle(self, message: str) -> str:
        """Processa slash command e retorna resposta."""
        cmd, args = parse_command(message)
        handler_name = COMMANDS.get(cmd)
        if not handler_name:
            return f"Comando desconhecido: {cmd}. Use /help."
        handler = getattr(self, handler_name)
        return await handler(args)

    async def switch_pipeline(self, args: str) -> str:
        """Muda contexto para outro pipeline. /resume [nome] [uuid-thread]"""
        parts = args.split()
        pipeline_name = parts[0] if parts else ""
        thread_uuid = parts[1] if len(parts) > 1 else None

        if not pipeline_name:
            return "Uso: /resume [pipeline] ou /resume [pipeline] [uuid-conversa]"

        # Busca por nome (case-insensitive)
        result = await self.db.execute(
            select(Pipeline).where(
                Pipeline.company_id == self.company_id,
                Pipeline.name.ilike(f"%{pipeline_name}%"),
            )
        )
        pipeline = result.scalar_one_or_none()

        if not pipeline:
            available = await self.db.execute(
                select(Pipeline.name).where(Pipeline.company_id == self.company_id)
            )
            names = "\n".join(f"  - {n[0]}" for n in available)
            return f"Pipeline '{pipeline_name}' nao encontrado.\nDisponiveis:\n{names}"

        # Thread especifico ou mais recente
        if thread_uuid:
            try:
                t_result = await self.db.execute(
                    select(Thread).where(
                        Thread.id == uuid.UUID(thread_uuid),
                        Thread.user_id == self.user_id,
                    )
                )
                thread = t_result.scalar_one_or_none()
                if not thread:
                    return f"Thread '{thread_uuid}' nao encontrado ou nao pertence a voce."
            except ValueError:
                return f"UUID invalido: {thread_uuid}"
        else:
            t_result = await self.db.execute(
                select(Thread).where(
                    Thread.user_id == self.user_id,
                    Thread.pipeline_id == pipeline.id,
                    Thread.is_active.is_(True),
                ).order_by(Thread.updated_at.desc()).limit(1)
            )
            thread = t_result.scalar_one_or_none()
            if not thread:
                thread = Thread(
                    pipeline_id=pipeline.id, user_id=self.user_id
                )
                self.db.add(thread)
                await self.db.flush()

        # Atualizar sessao ativa — sincronizar TODOS os canais do usuario
        all_sessions = await self.db.execute(
            select(ActiveSession).where(ActiveSession.user_id == self.user_id)
        )
        existing_channels = set()
        for s in all_sessions.scalars().all():
            s.active_thread_id = thread.id
            s.active_pipeline_id = pipeline.id
            existing_channels.add(s.channel)

        if self.channel not in existing_channels:
            self.db.add(ActiveSession(
                user_id=self.user_id,
                channel=self.channel,
                active_thread_id=thread.id,
                active_pipeline_id=pipeline.id,
            ))
        await self.db.flush()

        response = f"Conectado ao pipeline *{pipeline.name}*.\n"
        response += f"Thread: `{thread.id}`\n"

        # Status rapido
        if pipeline.databricks_job_id:
            try:
                svc = DatabricksService(self.db, self.company_id)
                summary = await svc.get_pipeline_summary(pipeline.databricks_job_id)
                response += f"Status: {summary.get('status', 'UNKNOWN')}\n"
            except Exception:
                pass

        response += "Em que posso ajudar?"
        return response

    async def list_pipelines(self, _args: str) -> str:
        result = await self.db.execute(
            select(Pipeline).where(Pipeline.company_id == self.company_id)
        )
        pipelines = result.scalars().all()
        if not pipelines:
            return "Nenhum pipeline configurado."
        lines = ["Pipelines disponiveis:"]
        for p in pipelines:
            lines.append(f"  - *{p.name}* (use /resume {p.name})")
        return "\n".join(lines)

    async def quick_status(self, _args: str) -> str:
        session_result = await self.db.execute(
            select(ActiveSession).where(
                ActiveSession.user_id == self.user_id,
                ActiveSession.channel == self.channel,
            )
        )
        session = session_result.scalar_one_or_none()
        if not session or not session.active_pipeline_id:
            return "Nenhum pipeline ativo. Use /resume [nome]."

        p_result = await self.db.execute(
            select(Pipeline).where(Pipeline.id == session.active_pipeline_id)
        )
        pipeline = p_result.scalar_one()

        if not pipeline.databricks_job_id:
            return f"*{pipeline.name}*\nStatus: NOT_CONFIGURED"

        svc = DatabricksService(self.db, self.company_id)
        summary = await svc.get_pipeline_summary(pipeline.databricks_job_id)
        return (
            f"*{pipeline.name}*\n"
            f"Status: {summary.get('status', 'UNKNOWN')}\n"
            f"Ultimo run: {summary.get('last_run_at', 'N/A')}"
        )

    async def list_threads(self, args: str) -> str:
        pipeline_name = args.strip() if args else None
        query = select(Thread).where(
            Thread.user_id == self.user_id, Thread.is_active.is_(True)
        )
        if pipeline_name:
            p_result = await self.db.execute(
                select(Pipeline.id).where(
                    Pipeline.company_id == self.company_id,
                    Pipeline.name.ilike(f"%{pipeline_name}%"),
                )
            )
            pid = p_result.scalar_one_or_none()
            if pid:
                query = query.where(Thread.pipeline_id == pid)

        result = await self.db.execute(
            query.order_by(Thread.updated_at.desc()).limit(10)
        )
        threads = result.scalars().all()
        if not threads:
            return "Nenhuma conversa encontrada."
        lines = ["Conversas recentes:"]
        for t in threads:
            title = t.title or "(sem titulo)"
            lines.append(f"  - `{t.id}` — {title[:50]}")
        lines.append("\nUse /resume [pipeline] [uuid] para retomar.")
        return "\n".join(lines)

    async def new_thread(self, args: str) -> str:
        pipeline_name = args.strip()
        if not pipeline_name:
            return "Uso: /new [pipeline-nome]"
        # Delega para switch_pipeline sem thread UUID (cria novo)
        return await self.switch_pipeline(pipeline_name)

    async def who_am_i(self, _args: str) -> str:
        session_result = await self.db.execute(
            select(ActiveSession).where(
                ActiveSession.user_id == self.user_id,
                ActiveSession.channel == self.channel,
            )
        )
        session = session_result.scalar_one_or_none()
        pipeline_name = "nenhum"
        thread_id = "nenhum"
        if session and session.active_pipeline_id:
            p = await self.db.execute(
                select(Pipeline.name).where(Pipeline.id == session.active_pipeline_id)
            )
            pipeline_name = p.scalar_one_or_none() or "nenhum"
            thread_id = str(session.active_thread_id) if session.active_thread_id else "nenhum"

        return (
            f"Canal: {self.channel}\n"
            f"Pipeline ativo: {pipeline_name}\n"
            f"Thread: {thread_id}"
        )

    async def change_model(self, args: str) -> str:
        """Tratado pelo ChannelMessageHandler — aqui e fallback pro web."""
        return "Use /model [opus|sonnet|haiku] para trocar o modelo."

    async def show_help(self, _args: str) -> str:
        return (
            "Comandos disponiveis:\n"
            "  /resume [pipeline] — conectar a um pipeline\n"
            "  /resume [pipeline] [uuid] — retomar conversa\n"
            "  /new [pipeline] — nova conversa\n"
            "  /pipelines — listar pipelines\n"
            "  /status — status do pipeline ativo\n"
            "  /threads [pipeline] — listar conversas\n"
            "  /model [opus|sonnet|haiku] — trocar modelo\n"
            "  /whoami — canal, pipeline, thread UUID da sessao atual\n"
            "  /help — esta mensagem"
        )
