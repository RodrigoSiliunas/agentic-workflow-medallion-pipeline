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

import re
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

# Modelo padrao para canais externos (fallback quando session.preferred_model e null)
_DEFAULT_MODEL = "sonnet"
_email_re = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Mensagens padrao
MSG_ONBOARDING = (
    "Ola! Sou o assistente Flowertex.\n\n"
    "Para comecar, preciso vincular seu numero a sua conta na plataforma.\n"
    "Por favor, digite o *email* que voce usa para fazer login:"
)
MSG_EMAIL_NOT_FOUND = (
    "Nao encontrei nenhuma conta com esse email.\n"
    "Verifique se digitou corretamente ou crie uma conta em nosso site primeiro."
)
MSG_LINKED = (
    "*Conta vinculada com sucesso!*\n"
    "Bem-vindo(a), {name}.\n\n"
    "Sou o assistente conversacional do *Flowertex*. Posso te dar status de "
    "pipelines, ler logs, consultar tabelas Delta, abrir PRs no GitHub e "
    "executar runs no Databricks — direto do WhatsApp.\n\n"
    "*Comandos disponiveis:*\n"
    "• `/pipelines` — lista os pipelines da sua empresa\n"
    "• `/resume <pipeline>` — entra no contexto de um pipeline pra fazer perguntas\n"
    "    Ex.: `/resume seguradora-whatsapp`\n"
    "• `/resume <pipeline> <uuid>` — retoma uma conversa anterior\n"
    "• `/new <pipeline>` — comeca uma conversa nova\n"
    "• `/status` — status do pipeline ativo (ultima run, falhas, duracao)\n"
    "• `/threads` — lista suas conversas recentes\n"
    "• `/model <opus|sonnet|haiku>` — troca o modelo Claude\n"
    "• `/whoami` — pipeline + thread atualmente ativos\n"
    "• `/help` — esta ajuda\n\n"
    "*Sem comando, eu respondo conversacionalmente* — pergunte coisas como:\n"
    "• \"qual o status do pipeline?\"\n"
    "• \"qual foi a ultima correcao automatica?\"\n"
    "• \"quantas linhas tem na bronze?\"\n"
    "• \"por que a run de ontem falhou?\"\n\n"
    "*Sugestao pra comecar:* digite `/pipelines` agora pra ver o que esta "
    "disponivel, depois `/resume <nome>` pra escolher um."
)
MSG_NO_PIPELINE_NONE_DEPLOYED = (
    "Voce ainda nao tem nenhum pipeline implantado.\n"
    "Crie um deploy na plataforma web primeiro, depois volte aqui."
)
MSG_PIPELINE_HINT = (
    "Voce tem pipeline(s) disponiveis mas nenhum ativo nesta conversa.\n"
    "Vou te ajudar com perguntas gerais sobre Databricks/Spark/Delta, mas pra "
    "consultar dados especificos de um pipeline preciso que voce escolha:\n\n"
    "{pipelines}\n\n"
    "Use `/resume <nome>` pra ativar um pipeline."
)
NO_PIPELINE_SYSTEM_PROMPT = (
    "Voce e o assistente conversacional do Flowertex Platform respondendo "
    "via canal externo (WhatsApp/Discord/Telegram).\n\n"
    "CONTEXTO IMPORTANTE: o usuario *nao tem pipeline ativo* na sessao atual. "
    "Pipelines disponiveis na conta dele:\n"
    "{pipelines_list}\n\n"
    "REGRAS RIGIDAS:\n"
    "1. Responda em portugues brasileiro (pt-BR), conciso, com markdown leve.\n"
    "2. Se a pergunta for *generalista* sobre Databricks, Delta Lake, PySpark, "
    "SQL, arquitetura medallion, conceitos de pipeline, etc — responda "
    "normalmente usando seu conhecimento.\n"
    "3. Se a pergunta exigir dados *especificos* de um pipeline (status, "
    "ultima run, logs, schema de tabela, contagem de linhas, PRs do repo, "
    "conteudo de notebook) — RECUSE educadamente e instrua o usuario a rodar "
    "`/resume <nome>` antes. Nao tente adivinhar qual pipeline.\n"
    "4. Voce nao deve chamar nenhuma tool nesta sessao — todas dependem de "
    "pipeline ativo.\n"
    "5. Se voce nao tiver certeza se a pergunta e generalista ou especifica, "
    "pergunte de volta qual pipeline o usuario quer consultar.\n\n"
    "EXEMPLOS:\n"
    '- "qual a diferenca entre Bronze e Silver?" -> responde (generalista).\n'
    '- "como funciona Delta Lake time travel?" -> responde (generalista).\n'
    '- "qual o status do meu pipeline?" -> recusa: "Pra te dar isso preciso '
    'saber qual pipeline. Use `/resume <nome>`. Disponiveis: ...".\n'
    '- "quantas linhas tem na bronze?" -> recusa, mesma instrucao.\n'
    '- "qual a ultima correcao automatica?" -> recusa, mesma instrucao.'
)
MSG_SESSION_CREATED = (
    "Sessao iniciada no pipeline *{pipeline}*.\n"
    "Pode perguntar o que quiser sobre seus dados!"
)


class ChannelMessageHandler:
    """Processa mensagens de canais externos."""

    def __init__(
        self,
        db: AsyncSession,
        omni: OmniService,
        startup_ts: datetime | None = None,
    ):
        self.db = db
        self.omni = omni
        # startup_ts: bot só processa mensagens AUTORADAS depois desse timestamp.
        # Sem ele, processa tudo (compat com chamadas legadas, ex: webhooks.py).
        self.startup_ts = startup_ts

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

        # Ignorar mensagens do proprio bot
        is_from_me = key.get("fromMe", False) or raw.get("isFromMe", False)
        if is_from_me:
            return

        # Ignorar grupos: @g.us aparece em qualquer JID + presenca de
        # `participant` indica msg recebida em grupo (mesmo se outro field for DM).
        is_group = (
            "@g.us" in sender_jid
            or "@g.us" in chat_id
            or "@g.us" in (key.get("remoteJid") or "")
            or bool(key.get("participant"))
        )
        if is_group:
            return

        # Ignorar sem texto
        if not text:
            return

        # Ignorar mensagens AUTORADAS antes do bot ligar.
        # WhatsApp/Baileys: rawPayload.messageTimestamp = unix seconds
        # quando a mensagem foi enviada pelo usuario (NAO quando o gateway
        # recebeu). Quando bot reconecta, baileys replay backlog inteiro
        # com receivedAt=now, mas messageTimestamp continua com hora original.
        if self.startup_ts is not None:
            msg_ts_raw = raw.get("messageTimestamp")
            try:
                msg_ts_int = int(msg_ts_raw) if msg_ts_raw is not None else None
            except (TypeError, ValueError):
                msg_ts_int = None
            if msg_ts_int is not None:
                msg_dt = datetime.fromtimestamp(msg_ts_int, tz=UTC)
                if msg_dt < self.startup_ts:
                    logger.info(
                        "Canal: mensagem pre-startup ignorada",
                        sender=sender_name,
                        msg_ts=msg_dt.isoformat(),
                        startup_ts=self.startup_ts.isoformat(),
                    )
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
            if _email_re.match(text.strip()):
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
                reply = await self._handle_model_command(text, user, channel, channel_user_id)
            else:
                reply = await handler.handle(text)

            await self._send(instance_id, sender_jid, reply)
            return

        # 3. Garantir sessao e thread
        session = await self._ensure_session(user, channel, channel_user_id)

        if not session.active_pipeline_id:
            await self._handle_no_pipeline(
                user=user,
                text=text,
                instance_id=instance_id,
                sender_jid=sender_jid,
            )
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
            await self._handle_no_pipeline(
                user=user,
                text=text,
                instance_id=instance_id,
                sender_jid=sender_jid,
            )
            return

        # Resolucao multi-provider: session > omni_instance > company default
        # session.preferred_model/provider tem precedencia sobre channel-level
        omni_instance = await self._get_omni_instance(instance_id)
        provider = (
            session.preferred_provider
            or (omni_instance.preferred_provider if omni_instance else None)
        )
        model = (
            session.preferred_model
            or (omni_instance.preferred_model if omni_instance else None)
            or _DEFAULT_MODEL
        )
        reply = await self._process_with_llm(
            user=user,
            pipeline=pipeline,
            thread_id=session.active_thread_id,
            text=text,
            model_override=model,
            provider_override=provider,
        )

        # 6. Salvar resposta
        if reply:
            assistant_msg = Message(
                thread_id=session.active_thread_id,
                role="assistant",
                content=reply,
                channel=channel,
                model=model,
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
        """Garante sessao ativa. Sincroniza cross-channel."""
        session = await self._get_session(user.id, channel)
        synced = await self._sync_from_sibling(session, user, channel, channel_user_id)
        if synced:
            return synced

        if session and session.active_thread_id and session.active_pipeline_id:
            return session

        # Sem sibling, sem sessao completa — criar nova
        return await self._create_fresh_session(session, user, channel, channel_user_id)

    async def _get_session(self, user_id: uuid.UUID, channel: str) -> ActiveSession | None:
        result = await self.db.execute(
            select(ActiveSession).where(
                ActiveSession.user_id == user_id,
                ActiveSession.channel == channel,
            )
        )
        return result.scalar_one_or_none()

    async def _sync_from_sibling(
        self, session: ActiveSession | None, user: User,
        channel: str, channel_user_id: str,
    ) -> ActiveSession | None:
        """Sincroniza com canal irmao mais recente. Retorna sessao ou None."""
        sibling_result = await self.db.execute(
            select(ActiveSession).where(
                ActiveSession.user_id == user.id,
                ActiveSession.channel != channel,
                ActiveSession.active_thread_id.isnot(None),
                ActiveSession.active_pipeline_id.isnot(None),
            ).order_by(ActiveSession.updated_at.desc()).limit(1)
        )
        sibling = sibling_result.scalar_one_or_none()
        if not sibling:
            return None

        if session:
            if session.active_thread_id != sibling.active_thread_id:
                session.active_thread_id = sibling.active_thread_id
                session.active_pipeline_id = sibling.active_pipeline_id
                session.channel_user_id = channel_user_id
                await self.db.commit()
            return session

        session = ActiveSession(
            user_id=user.id, channel=channel,
            channel_user_id=channel_user_id,
            active_thread_id=sibling.active_thread_id,
            active_pipeline_id=sibling.active_pipeline_id,
        )
        self.db.add(session)
        await self.db.commit()
        return session

    async def _create_fresh_session(
        self, session: ActiveSession | None, user: User,
        channel: str, channel_user_id: str,
    ) -> ActiveSession:
        """Cria sessao nova com primeiro pipeline e thread existente ou novo."""
        pipeline_result = await self.db.execute(
            select(Pipeline).where(Pipeline.company_id == user.company_id)
            .order_by(Pipeline.created_at.desc()).limit(1)
        )
        pipeline = pipeline_result.scalar_one_or_none()

        if not pipeline:
            if not session:
                session = ActiveSession(
                    user_id=user.id, channel=channel,
                    channel_user_id=channel_user_id,
                )
                self.db.add(session)
                await self.db.flush()
            return session

        thread = await self._find_or_create_thread(user, pipeline)

        if session:
            session.active_thread_id = thread.id
            session.active_pipeline_id = pipeline.id
            session.channel_user_id = channel_user_id
        else:
            session = ActiveSession(
                user_id=user.id, channel=channel,
                channel_user_id=channel_user_id,
                active_thread_id=thread.id,
                active_pipeline_id=pipeline.id,
            )
            self.db.add(session)

        await self.db.commit()
        logger.info("Canal: sessao criada", pipeline=pipeline.name, thread=str(thread.id))
        return session

    # --- LLM ---

    async def _find_or_create_thread(self, user: User, pipeline: Pipeline) -> Thread:
        """Busca thread ativo mais recente ou cria um novo."""
        result = await self.db.execute(
            select(Thread).where(
                Thread.user_id == user.id,
                Thread.pipeline_id == pipeline.id,
                Thread.is_active.is_(True),
            ).order_by(Thread.updated_at.desc()).limit(1)
        )
        thread = result.scalar_one_or_none()
        if not thread:
            thread = Thread(
                pipeline_id=pipeline.id,
                user_id=user.id,
                title=f"Canal — {datetime.now(UTC).strftime('%d/%m %H:%M')}",
            )
            self.db.add(thread)
            await self.db.flush()
        return thread

    async def _process_with_llm(
        self, user: User, pipeline: Pipeline,
        thread_id: uuid.UUID, text: str,
        model_override: str = "sonnet",
        provider_override: str | None = None,
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

        full_response = ""
        try:
            async for event in orchestrator.process_message(
                user_message=text,
                pipeline_job_id=pipeline.databricks_job_id or 0,
                conversation_history=history[:-1],
                model_override=model_override,
                provider_override=provider_override,
                pipeline_id=pipeline.id,
            ):
                if event["type"] == "token":
                    full_response += event["content"]
        except Exception as exc:
            logger.error("LLM processing error", error=str(exc))
            return ""

        return full_response.strip()

    async def _handle_no_pipeline(
        self, user: User, text: str, instance_id: str, sender_jid: str,
    ) -> None:
        """Sem pipeline ativo: lista disponiveis + roteia LLM com guard prompt.

        Generalist Q (Databricks/Spark/Delta conceitos) → LLM responde.
        Pipeline-specific Q → LLM recusa e pede /resume <nome>.
        """
        pipelines_result = await self.db.execute(
            select(Pipeline).where(Pipeline.company_id == user.company_id)
            .order_by(Pipeline.created_at.desc())
        )
        pipelines = pipelines_result.scalars().all()

        if not pipelines:
            await self._send(instance_id, sender_jid, MSG_NO_PIPELINE_NONE_DEPLOYED)
            return

        pipelines_list = "\n".join(
            f"- *{p.name}* (use `/resume {p.name}`)" for p in pipelines
        )
        system_prompt = NO_PIPELINE_SYSTEM_PROMPT.format(
            pipelines_list=pipelines_list
        )

        # Pre-aviso curto (so na primeira mensagem da conversa pode ser util,
        # mas pra simplicidade enviamos sempre — usuario percebe rapido)
        # Nao enviamos hint aqui; deixamos LLM responder direto pra fluidez.

        orchestrator = LLMOrchestrator(self.db, user.company_id, user.name or "usuario")
        full_response = ""
        try:
            async for event in orchestrator.process_message(
                user_message=text,
                pipeline_job_id=0,
                conversation_history=[],
                system_prompt_override=system_prompt,
            ):
                if event["type"] == "token":
                    full_response += event["content"]
        except Exception as exc:
            logger.error("LLM no-pipeline error", error=str(exc))
            full_response = ""

        if not full_response.strip():
            full_response = MSG_PIPELINE_HINT.format(pipelines=pipelines_list)

        await self._send(instance_id, sender_jid, full_response.strip())

    # --- Slash: /model ---

    async def _handle_model_command(
        self, text: str, user: User, channel: str, channel_user_id: str,
    ) -> str:
        """Trata /model [opus|sonnet|haiku]. Salva preferencia na sessao (per-user)."""
        session = await self._ensure_session(user, channel, channel_user_id)
        current = session.preferred_model or _DEFAULT_MODEL

        parts = text.strip().split()
        if len(parts) < 2:
            return (
                f"Modelo atual: *{current}*\n\n"
                "Uso: /model [opus|sonnet|haiku]\n"
                "- *opus* — Mais capaz, mais lento\n"
                "- *sonnet* — Equilibrado (padrao)\n"
                "- *haiku* — Mais rapido, mais leve"
            )

        model = parts[1].lower()
        valid = {"opus", "sonnet", "haiku"}
        if model not in valid:
            return f"Modelo invalido. Opcoes: {', '.join(sorted(valid))}"

        session.preferred_model = model
        await self.db.commit()
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

    async def _get_omni_instance(self, omni_id: str):
        """Lookup OmniInstance pelo omni_instance_id (string do Omni gateway)."""
        from app.models.channel import OmniInstance

        result = await self.db.execute(
            select(OmniInstance).where(OmniInstance.omni_instance_id == omni_id)
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
