"""Dispara o pipeline em chaos mode para testar o agente AI.

Uso:
  python deploy/trigger_chaos.py bronze_schema        # schema invalido
  python deploy/trigger_chaos.py silver_null          # NULLs no dedup
  python deploy/trigger_chaos.py gold_divide_zero     # divisao por zero
  python deploy/trigger_chaos.py validation_strict    # threshold impossivel

O chaos mode injeta uma falha controlada na camada escolhida.
Fluxo esperado: task com erro -> agent_post faz rollback -> observer_trigger
dispara o Observer Agent -> cria PR para dev.
"""

import os
import sys

from databricks.sdk import WorkspaceClient

VALID_MODES = [
    "bronze_schema",
    "silver_null",
    "gold_divide_zero",
    "validation_strict",
]
WORKFLOW_NAME = "medallion_pipeline_whatsapp"


def find_latest_job(workspace: WorkspaceClient, name: str):
    """Escolhe o job mais novo para evitar execucoes em definicoes antigas."""
    jobs = list(workspace.jobs.list(name=name))
    if not jobs:
        return None
    return max(jobs, key=lambda job: int(job.job_id))


def trigger_chaos(mode: str):
    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    job = find_latest_job(w, WORKFLOW_NAME)
    if not job:
        print(f"ERRO: Job '{WORKFLOW_NAME}' nao encontrado")
        sys.exit(1)

    job_id = job.job_id
    print(f"Job: {job.settings.name} (ID: {job_id})")
    print(f"Chaos mode: {mode}")
    print()

    run = w.jobs.run_now(
        job_id=job_id,
        notebook_params={"chaos_mode": mode},
    )

    print(f"Run disparado: {run.run_id}")
    host = os.environ["DATABRICKS_HOST"]
    print(f"URL: {host}/jobs/{job_id}/runs/{run.run_id}")
    print()
    print("Aguarde o pipeline terminar e verifique:")
    print("  1. observer_trigger output (disparo automatico do Observer)")
    print("  2. job workflow_observer_agent executado com o source_run_id correto")
    print("  3. gh pr list (PR criado automaticamente)")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in VALID_MODES:
        print("Uso: python deploy/trigger_chaos.py <modo>")
        print()
        print("Modos disponiveis:")
        for m in VALID_MODES:
            print(f"  {m}")
        sys.exit(1)

    trigger_chaos(sys.argv[1])
