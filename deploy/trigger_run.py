"""Dispara execucao manual do Workflow.

Uso: python deploy/trigger_run.py <job_id>
"""

import os
import sys

from databricks.sdk import WorkspaceClient


def trigger(job_id: int):
    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    run = w.jobs.run_now(job_id=job_id)
    print(f"Run disparado: run_id={run.run_id}")
    print(f"Acompanhe em: {os.environ['DATABRICKS_HOST']}/jobs/{job_id}/runs/{run.run_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python deploy/trigger_run.py <job_id>")
        sys.exit(1)
    trigger(int(sys.argv[1]))
