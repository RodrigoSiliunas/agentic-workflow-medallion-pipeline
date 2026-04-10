"""Atualiza o status de um PR do Observer na tabela `observer.diagnostics`.

Chamado pela GitHub Action `.github/workflows/observer-feedback.yml` quando
um PR com branch `fix/agent-auto-*` eh fechado ou mergeado. Alimenta o loop
de feedback que permite medir taxa de merge, tempo medio de resolucao e
eficacia do agente autonomo ao longo do tempo.

Uso:
    python deploy/update_pr_feedback.py --pr-number 5 --status merged
    python deploy/update_pr_feedback.py --pr-number 9 --status closed

Requer envs: DATABRICKS_HOST, DATABRICKS_TOKEN.
Opcional: PIPELINE_CATALOG (default: medallion).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from databricks.sdk import WorkspaceClient


def get_warehouse(workspace: WorkspaceClient):
    """Retorna um SQL warehouse ligado (inicia se necessario)."""
    warehouses = list(workspace.warehouses.list())
    if not warehouses:
        print("ERRO: nenhum SQL Warehouse disponivel")
        sys.exit(1)

    wh = warehouses[0]
    if str(wh.state) != "State.RUNNING":
        print(f"Iniciando warehouse '{wh.name}'...")
        workspace.warehouses.start(wh.id)
        for _ in range(30):
            time.sleep(5)
            wh = workspace.warehouses.get(wh.id)
            if str(wh.state) == "State.RUNNING":
                break
    print(f"Warehouse: {wh.name} ({wh.id})")
    return wh


def update_pr_feedback(
    workspace: WorkspaceClient,
    warehouse_id: str,
    catalog: str,
    pr_number: int,
    pr_status: str,
) -> None:
    """Executa o UPDATE via SQL warehouse."""
    if pr_status not in ("merged", "closed"):
        print(f"ERRO: pr_status invalido: {pr_status!r}")
        sys.exit(2)

    feedback = "fix_accepted" if pr_status == "merged" else "fix_rejected"
    table = f"{catalog}.observer.diagnostics"

    # Conta quantos records existem antes para log informativo
    count_sql = f"SELECT COUNT(*) FROM {table} WHERE pr_number = {pr_number}"
    count_result = workspace.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=count_sql,
        wait_timeout="30s",
    )
    if count_result.status.error:
        print(f"ERRO ao contar: {count_result.status.error.message}")
        sys.exit(3)

    data = count_result.result.data_array if count_result.result else []
    match_count = int(data[0][0]) if data else 0
    if match_count == 0:
        print(
            f"AVISO: nenhum record com pr_number={pr_number} encontrado "
            f"em {table} — nada a atualizar"
        )
        return

    update_sql = (
        f"UPDATE {table} "
        f"SET pr_status = '{pr_status}', "
        f"    pr_resolved_at = current_timestamp(), "
        f"    resolution_time_hours = "
        f"        (unix_timestamp(current_timestamp()) - unix_timestamp(timestamp)) / 3600.0, "
        f"    feedback = '{feedback}' "
        f"WHERE pr_number = {pr_number}"
    )

    result = workspace.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=update_sql,
        wait_timeout="50s",
    )
    if result.status.error:
        print(f"ERRO ao atualizar: {result.status.error.message}")
        sys.exit(4)

    plural = "s" if match_count != 1 else ""
    print(
        f"OK: PR #{pr_number} -> status={pr_status}, feedback={feedback} "
        f"({match_count} record{plural} atualizado{plural})"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pr-number",
        type=int,
        required=True,
        help="Numero do PR no GitHub",
    )
    parser.add_argument(
        "--status",
        choices=["merged", "closed"],
        required=True,
        help="Status final do PR",
    )
    parser.add_argument(
        "--catalog",
        default=os.environ.get("PIPELINE_CATALOG", "medallion"),
        help="Nome do catalog Unity (default: medallion)",
    )
    args = parser.parse_args()

    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    if not host or not token:
        print("ERRO: DATABRICKS_HOST e DATABRICKS_TOKEN sao obrigatorios")
        sys.exit(1)

    w = WorkspaceClient(host=host, token=token)
    wh = get_warehouse(w)

    update_pr_feedback(
        workspace=w,
        warehouse_id=wh.id,
        catalog=args.catalog,
        pr_number=args.pr_number,
        pr_status=args.status,
    )


if __name__ == "__main__":
    main()
