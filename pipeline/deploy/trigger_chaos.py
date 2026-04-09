"""Dispara o pipeline em chaos mode para testar o agente AI.

Uso:
  python deploy/trigger_chaos.py bronze_schema       # schema invalido
  python deploy/trigger_chaos.py silver_null          # NULLs no dedup
  python deploy/trigger_chaos.py gold_divide_zero     # divisao por zero
  python deploy/trigger_chaos.py validation_strict    # threshold impossivel

O chaos mode injeta uma falha controlada na camada escolhida.
O agent_post deve: detectar → rollback → Claude API → criar PR para dev.
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


def trigger_chaos(mode: str):
    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    # Encontrar o job do pipeline
    jobs = list(w.jobs.list(name="medallion_pipeline_whatsapp"))
    if not jobs:
        print("ERRO: Job 'medallion_pipeline_whatsapp' nao encontrado")
        sys.exit(1)

    job_id = jobs[0].job_id
    print(f"Job: {jobs[0].settings.name} (ID: {job_id})")
    print(f"Chaos mode: {mode}")
    print()

    # Dispara com o chaos_mode como parametro do notebook
    # O agent_pre le do widget e propaga via task values
    run = w.jobs.run_now(
        job_id=job_id,
        notebook_params={"chaos_mode": mode},
    )

    print(f"Run disparado: {run.run_id}")
    host = os.environ["DATABRICKS_HOST"]
    print(f"URL: {host}/jobs/{job_id}/runs/{run.run_id}")
    print()
    print("Aguarde o pipeline terminar e verifique:")
    print("  1. agent_post output (diagnostico do Claude)")
    print("  2. gh pr list (PR criado automaticamente)")
    print("  3. git branch -a | grep fix/ (branch do fix)")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in VALID_MODES:
        print("Uso: python deploy/trigger_chaos.py <modo>")
        print()
        print("Modos disponiveis:")
        for m in VALID_MODES:
            print(f"  {m}")
        sys.exit(1)

    trigger_chaos(sys.argv[1])
