"""Channel Message Handler — processa mensagens de WhatsApp/Discord/Telegram.

Fluxo:
1. Extrair texto e sender do evento Omni
2. Ignorar grupos e mensagens sem texto
3. Resolver identidade: phone → ChannelIdentity → User
4. Se nao vinculado, iniciar onboarding
5. Resolver sessao ativa (ActiveSession → Thread + Pipeline)
6. Se slash command, despachar para SlashCommandHandler
7. Se mensagem normal, processar via LLMOrchestrator
8. Enviar resposta via Omni
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import ActiveSession, ChannelIdentity
from app.models.chat import Message, Thread
from app.models.pipeline import Pipeline
from app.models.user import User
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.omni_service import OmniService
from app.services.slash_commands import SlashCommandHandler, is_slash_command

logger = structlog.get_logger()

# Modelo padrao para canais externos
DEFAULT_MODEL = "sonnet"

# Mensagens padrao
MSG_ONBOARDING = (
    "Ola! Sou o assistente Safatechx.\n\n"
    "Para comecar, preciso vincular seu numero a sua conta na plataforma.\n"
    "Por favor, digite o *email* que voce usa para fazer login:"
)
MSG_EMAIL_NOT_FOUND = (
    "Nao encontrei nenhuma conta com esse email.\n"
    "Verifique se digitou corretamente ou crie uma conta em nosso site primeiro."
)
MSG_LINKED = (
    "Conta vinculada com sucesso! Bem-vindo(a), {name}.\n\n"
    "Agora voce pode usar o chat como se estivesse na plataforma.\n"
    "Digite /help para ver os comandos disponiveis."
)
MSG_NO_PIPELINE = (
    "Voce ainda nao tem nenhum pipeline implantado.\n"
    "Crie um deploy na plataforma web primeiro, depois volte aqui."
)
MSG_SESSION_CREATED = (
    "Sessao iniciada no pipeline *{pipeline}*.\n"
    "Pode perguntar o que quiser sobre seus dados!"
)


class ChannelMessageHandler:
    """Processa mensagens de canais externos."""

    def __init__(self, db: AsyncSession, omni: OmniService):
        self.db = db
        self.omni = omni

    async def handle_event(self, event: dict) -> None:
        """Processa um evento de mensagem do Omni."""
        text = (event.get("textContent") or "").strip()
        instance_id = event.get("instanceId", "")
        chat_id = event.get("chatId", "")

        # Extrair dados do remetente
        raw = event.get("rawPayload", {})
        key = raw.get("key", {})
        sender_jid = key.get("remoteJidAlt") or key.get("remoteJid") or chat_id
        sender_name = raw.get("pushName", "")

        # Ignorar grupos
        if "@g.us" in sender_jid or "@g.us" in chat_id:
            return

        # Ignorar sem texto
        if not text:
            return

        # Detectar canal
        channel = self._detect_channel(event)

        # Extrair phone/user_id do JID (ex: 5511963023837@s.whatsapp.net → 5511963023837)
        channel_user_id = sender_jid.split("@")[0] if "@" in sender_jid else sender_jid

        logger.info(
            "Canal: mensagem recebida",
            sender=sender_name, channel=channel, text=text[:60],
        )

        # 1. Resolver identidade
        identity = await self._get_identity(channel, channel_user_id)

        if not identity:
            # Checar se e resposta de onboarding (email)
            if "@" in text and "." in text:
                await self._try_link_account(
                    channel, channel_user_id, text.strip().lower(),
                    instance_id, sender_jid,
                )
            else:
                await self._send(instance_id, sender_jid, MSG_ONBOARDING)
            return

        user = await self._get_user(identity.user_id)
        if not user:
            await self._send(instance_id, sender_jid, MSG_ONBOARDING)
            return

        # 2. Checar slash commands
        if is_slash_command(text):
            # Garantir sessao existe
            session = await self._ensure_session(user, channel, channel_user_id)
            handler = SlashCommandHandler(
                db=self.db,
                user_id=user.id,
                company_id=user.company_id,
                channel=channel,
            )

            # Comando especial: /model
            if text.lower().startswith("/model"):
                reply = await self._handle_model_command(text, user)
            else:
                reply = await handler.handle(text)

            await self._send(instance_id, sender_jid, reply)
            return

        # 3. Garantir sessao e thread
        session = await self._ensure_session(user, channel, channel_user_id)

        if not session.active_pipeline_id:
            await self._send(instance_id, sender_jid, MSG_NO_PIPELINE)
            return

        # 4. Salvar mensagem do usuario
        user_msg = Message(
            thread_id=session.active_thread_id,
            role="user",
            content=text,
            channel=channel,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # 5. Processar com LLM
        pipeline = await self._get_pipeline(session.active_pipeline_id)
        if not pipeline:
            await self._send(instance_id, sender_jid, MSG_NO_PIPELINE)
            return

        reply = await self._process_with_llm(
            user=user,
            pipeline=pipeline,
            thread_id=session.active_thread_id,
            text=text,
        )

        # 6. Salvar resposta
        if reply:
            assistant_msg = Message(
                thread_id=session.active_thread_id,
                role="assistant",
                content=reply,
                channel=channel,
                model=DEFAULT_MODEL,
            )
            self.db.add(assistant_msg)
            await self.db.commit()

            # 7. Enviar via Omni
            await self._send(instance_id, sender_jid, reply)
        else:
            await self._send(
                instance_id, sender_jid,
                "Desculpe, nao consegui processar sua mensagem. Tente novamente."
            )

    # --- Identidade ---

    async def _get_identity(
        self, channel: str, channel_user_id: str
    ) -> ChannelIdentity | None:
        result = await self.db.execute(
            select(ChannelIdentity).where(
                ChannelIdentity.channel == channel,
                ChannelIdentity.channel_user_id == channel_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _try_link_account(
        self, channel: str, channel_user_id: str, email: str,
        instance_id: str, sender_jid: str,
    ) -> None:
        """Tenta vincular canal ao usuario pelo email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            await self._send(instance_id, sender_jid, MSG_EMAIL_NOT_FOUND)
            return

        # Criar identidade
        identity = ChannelIdentity(
            user_id=user.id,
            channel=channel,
            channel_user_id=channel_user_id,
            verified=True,
        )
        self.db.add(identity)
        await self.db.commit()

        logger.info("Canal: identidade vinculada", email=email, channel=channel)
        await self._send(
            instance_id, sender_jid,
            MSG_LINKED.format(name=user.name or email),
        )

    # --- Sessao ---

    async def _ensure_session(
        self, user: User, channel: str, channel_user_id: str,
    ) -> ActiveSession:
        """Garante sessao ativa. Herda thread/pipeline de outro canal se existir."""
        result = await self.db.execute(
            select(ActiveSession).where(
                ActiveSession.user_id == user.id,
                ActiveSession.channel == channel,
            )
        )
        session = result.scalar_one_or_none()

        # SEMPRE sincronizar com o canal mais recentemente atualizado
        sibling_result = await self.db.execute(
            select(ActiveSession).where(
                ActiveSession.user_id == user.id,
                ActiveSession.channel != channel,
                ActiveSession.active_thread_id.isnot(None),
                ActiveSession.active_pipeline_id.isnot(None),
            ).order_by(ActiveSession.updated_at.desc()).limit(1)
        )
        sibling = sibling_result.scalar_one_or_none()

        if sibling:
            if session:
                if session.active_thread_id != sibling.active_thread_id:
                    session.active_thread_id = sibling.active_thread_id
                    session.active_pipeline_id = sibling.active_pipeline_id
                    session.channel_user_id = channel_user_id
                    await self.db.commit()
                    logger.info("Canal: sessao sincronizada", channel=channel, thread=str(sibling.active_thread_id))
                return session
            else:
                session = ActiveSession(
                    user_id=user.id,
                    channel=channel,
                    channel_user_id=channel_user_id,
                    active_thread_id=sibling.active_thread_id,
                    active_pipeline_id=sibling.active_pipeline_id,
                )
                self.db.add(session)
                await self.db.commit()
                return session

        if session and session.active_thread_id and session.active_pipeline_id:
            return session

        # Nenhuma sessao em nenhum canal — buscar pipeline
        pipeline_result = await self.db.execute(
            select(Pipeline)
            .where(Pipeline.company_id == user.company_id)
            .order_by(Pipeline.created_at.desc())
            .limit(1)
        )
        pipeline = pipeline_result.scalar_one_or_none()

        if not pipeline:
            if not session:
                session = ActiveSession(
                    user_id=user.id,
                    channel=channel,
                    channel_user_id=channel_user_id,
                )
                self.db.add(session)
                await self.db.flush()
            return session

        # Reutilizar thread mais recente do usuario neste pipeline
        thread_result = await self.db.execute(
            select(Thread).where(
                Thread.user_id == user.id,
                Thread.pipeline_id == pipeline.id,
                Thread.is_active.is_(True),
            ).order_by(Thread.updated_at.desc()).limit(1)
        )
        thread = thread_result.scalar_one_or_none()

        if not thread:
            thread = Thread(
                pipeline_id=pipeline.id,
                user_id=user.id,
                title=f"Canal — {datetime.now(UTC).strftime('%d/%m %H:%M')}",
            )
            self.db.add(thread)
            await self.db.flush()

        if session:
            session.active_thread_id = thread.id
            session.active_pipeline_id = pipeline.id
            session.channel_user_id = channel_user_id
        else:
            session = ActiveSession(
                user_id=user.id,
                channel=channel,
                channel_user_id=channel_user_id,
                active_thread_id=thread.id,
                active_pipeline_id=pipeline.id,
            )
            self.db.add(session)

        await self.db.commit()
        logger.info("Canal: sessao criada", pipeline=pipeline.name, thread=str(thread.id))
        return session

    # --- LLM ---

    async def _process_with_llm(
        self, user: User, pipeline: Pipeline,
        thread_id: uuid.UUID, text: str,
    ) -> str:
        """Processa mensagem com LLMOrchestrator e retorna resposta completa."""
        orchestrator = LLMOrchestrator(self.db, user.company_id, user.name or "usuario")

        # Carregar historico recente
        history_result = await self.db.execute(
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at.desc())
            .limit(20)
        )
        history = [
            {"role": m.role, "content": m.content}
            for m in reversed(history_result.scalars().all())
            if m.role in ("user", "assistant")
        ]

        # Coletar resposta completa (sem streaming para canais externos)
        full_response = ""
        try:
            async for event in orchestrator.process_message(
                user_message=text,
                pipeline_job_id=pipeline.databricks_job_id or 0,
                conversation_history=history[:-1],
                model_override=DEFAULT_MODEL,
            ):
                if event["type"] == "token":
                    full_response += event["content"]
        except Exception as exc:
            logger.error("LLM processing error", error=str(exc))
            return ""

        return full_response.strip()

    # --- Slash: /model ---

    async def _handle_model_command(self, text: str, user: User) -> str:
        """Trata o comando /model [opus|sonnet|haiku]."""
        global DEFAULT_MODEL
        parts = text.strip().split()
        if len(parts) < 2:
            return (
                f"Modelo atual: *{DEFAULT_MODEL}*\n\n"
                "Uso: /model [opus|sonnet|haiku]\n"
                "- *opus* — Mais capaz, mais lento\n"
                "- *sonnet* — Equilibrado (padrao)\n"
                "- *haiku* — Mais rapido, mais leve"
            )

        model = parts[1].lower()
        valid = {"opus", "sonnet", "haiku"}
        if model not in valid:
            return f"Modelo invalido. Opcoes: {', '.join(sorted(valid))}"

        DEFAULT_MODEL = model
        return f"Modelo alterado para *{model}*."

    # --- Helpers ---

    async def _get_user(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _get_pipeline(self, pipeline_id: uuid.UUID) -> Pipeline | None:
        result = await self.db.execute(
            select(Pipeline).where(Pipeline.id == pipeline_id)
        )
        return result.scalar_one_or_none()

    async def _send(self, instance_id: str, to: str, text: str) -> None:
        """Envia mensagem via Omni. Quebra em chunks de 4000 chars (limite WhatsApp)."""
        max_len = 4000
        for i in range(0, len(text), max_len):
            chunk = text[i:i + max_len]
            try:
                await self.omni.send_message(instance_id, to, chunk)
            except Exception as exc:
                logger.error("Falha ao enviar mensagem", error=str(exc))
                break

    @staticmethod
    def _detect_channel(event: dict) -> str:
        channel = event.get("channel", "")
        if "whatsapp" in channel:
            return "whatsapp"
        if "discord" in channel:
            return "discord"
        if "telegram" in channel:
            return "telegram"
        return "whatsapp"
