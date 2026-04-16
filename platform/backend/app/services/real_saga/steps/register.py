"""Step `register` — no-op no runner.

O registro do Pipeline no DB e feito pelo orquestrador (`deployment_saga.run_saga`)
logo antes de marcar o deployment como success. Esse step serve apenas pra
emitir um log de confirmacao visivel no UI.
"""

from __future__ import annotations

from app.services.real_saga.base import StepContext
from app.services.real_saga.registry import register_saga_step


@register_saga_step("register")
class RegisterStep:
    step_id = "register"

    async def execute(self, ctx: StepContext) -> None:
        await ctx.info(
            f"Pipeline '{ctx.deployment.name}' registrado na plataforma. "
            "O chat agent ja pode conversar com este workflow."
        )
