"""Step `trigger` — dispara o primeiro run do workflow e acompanha ate concluir.

Poll com backoff exponencial limitado a 30s. Se o run entrar em terminal state
(TERMINATED/SKIPPED/INTERNAL_ERROR), o step checa o `result_state` e emite um
log final informativo. Falha do pipeline NAO faz este step falhar — os logs
ficam disponiveis no UI do Databricks e o Observer Agent ja esta armado pra
diagnosticar.
"""

from __future__ import annotations

import asyncio

from databricks.sdk.service.jobs import RunLifeCycleState

from app.services.real_saga.base import StepContext
from app.services.real_saga.databricks_client import workspace_client
from app.services.real_saga.registry import register_saga_step

_POLL_TIMEOUT_SECONDS = 1800  # 30min — cobre o timeout_seconds do pipeline (3600s) parcialmente
_POLL_INTERVAL_INITIAL = 10
_POLL_INTERVAL_MAX = 30

_TERMINAL = {
    RunLifeCycleState.TERMINATED,
    RunLifeCycleState.SKIPPED,
    RunLifeCycleState.INTERNAL_ERROR,
}


@register_saga_step("trigger")
class TriggerStep:
    step_id = "trigger"

    async def execute(self, ctx: StepContext) -> None:
        job_id = ctx.shared.workflow_job_id
        if not job_id:
            raise RuntimeError(
                "trigger step sem workflow_job_id — step `workflow` deve rodar antes"
            )

        w = workspace_client(ctx.credentials)

        await ctx.info(f"Disparando primeiro run do job {job_id}")

        def _run_now() -> int:
            waiter = w.jobs.run_now(job_id=job_id)
            # waiter.run_id expoe o run_id imediatamente
            return int(waiter.run_id)

        run_id = await asyncio.to_thread(_run_now)
        await ctx.info(
            f"Run iniciado: run_id={run_id} "
            f"(acompanhe em {ctx.credentials.databricks_host}/jobs/{job_id}/runs/{run_id})"
        )
        ctx.shared.run_id = run_id

        await self._poll_until_done(ctx, w, run_id)

    @staticmethod
    async def _poll_until_done(ctx: StepContext, w, run_id: int) -> None:
        interval = _POLL_INTERVAL_INITIAL
        elapsed = 0
        last_state: str | None = None

        while elapsed < _POLL_TIMEOUT_SECONDS:

            def _get() -> tuple[RunLifeCycleState | None, str | None]:
                run = w.jobs.get_run(run_id=run_id)
                life_cycle = run.state.life_cycle_state if run.state else None
                result = run.state.result_state if run.state else None
                return (life_cycle, str(result) if result else None)

            life_cycle, result = await asyncio.to_thread(_get)
            state_label = str(life_cycle).replace("RunLifeCycleState.", "") if life_cycle else "?"

            if state_label != last_state:
                await ctx.info(f"  run {run_id}: {state_label}")
                last_state = state_label

            if life_cycle in _TERMINAL:
                if result:
                    await ctx.info(f"Run {run_id} finalizado: result={result}")
                else:
                    await ctx.info(f"Run {run_id} finalizado (sem result_state)")
                return

            await asyncio.sleep(interval)
            elapsed += interval
            interval = min(interval + 5, _POLL_INTERVAL_MAX)

        await ctx.warn(
            f"Poll de 30min expirou — run {run_id} continua rodando. "
            "Acompanhe direto no Databricks UI."
        )
