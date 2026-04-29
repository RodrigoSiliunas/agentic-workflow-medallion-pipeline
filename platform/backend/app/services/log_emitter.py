"""LogEmitter — extrai o closure `emit_log` do deployment_saga (T4 Phase 5).

Antes: closure capturava `db`, `deployment_id`, `cancel_event`, `log_lock`,
publisher SSE. Tinha `noqa: B023` pra silenciar warning de variable
binding em loop. Dava pra misturar lifecycle + dependencies num fechamento
dificil de testar.

Depois: classe tipada com deps injetadas. Instanciada uma vez por step,
callable — compatível com `EmitLogFn = Callable[[str, str, str | None], Awaitable[None]]`
usada pelo step runner.

Benefícios:
- Testável isoladamente (sem DB real via AsyncMock)
- Sem loop variable binding pitfall
- Thread safety explícita via asyncio.Lock
- Publisher injetado (tests passam fake/NullPublisher)
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import DeploymentLog

logger = structlog.get_logger()

PublishFn = Callable[[str, dict[str, Any]], Awaitable[None]]


class LogEmitter:
    """Callable que persiste log no DB + publica no SSE backend.

    Instanciar uma vez por step (ou por deploy) com:
    - db: async session ja aberto pelo run_saga
    - deployment_id: uuid do deploy
    - cancel_event: asyncio.Event sinalizando cancel do usuario
    - publish: coroutine que broadcasta o evento pro backend pub/sub
    - log_lock: asyncio.Lock compartilhado — evita crash no SQLAlchemy
      quando flushes concorrentes (ex: asyncio.gather no validate step)
      executam ao mesmo tempo

    Uso:
        emit = LogEmitter(db, dep_id, cancel_event, publish, log_lock)
        await emit("info", "Starting bucket creation", "s3")
    """

    def __init__(
        self,
        db: AsyncSession,
        deployment_id: uuid.UUID,
        cancel_event: asyncio.Event,
        publish: PublishFn,
        log_lock: asyncio.Lock,
    ) -> None:
        self._db = db
        self._deployment_id = deployment_id
        self._cancel_event = cancel_event
        self._publish = publish
        self._log_lock = log_lock

    async def __call__(
        self,
        level: str,
        message: str,
        step_id: str | None = None,
    ) -> None:
        """Emite uma linha de log.

        Pre-gera id client-side (UUID4) — elimina flush dentro do lock.
        Commit batched no boundary de step. SSE publica imediato apos
        liberar o lock pra reduzir contention quando ha logs paralelos
        (ex: upload com ThreadPoolExecutor).
        """
        if self._cancel_event.is_set():
            return

        log_id = uuid.uuid4()
        async with self._log_lock:
            self._db.add(
                DeploymentLog(
                    id=log_id,
                    deployment_id=self._deployment_id,
                    level=level,
                    message=message,
                    step_id=step_id,
                )
            )

        log_ts = datetime.now(UTC).isoformat()
        dep_id_str = str(self._deployment_id)
        await self._publish(
            dep_id_str,
            {
                "type": "log",
                "deployment_id": dep_id_str,
                "data": {
                    "id": str(log_id),
                    "level": level,
                    "message": message,
                    "step_id": step_id,
                    "timestamp": log_ts,
                },
            },
        )
