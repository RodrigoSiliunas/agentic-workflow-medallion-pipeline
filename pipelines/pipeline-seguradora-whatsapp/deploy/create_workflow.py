"""Cria o Databricks Workflow ETL Medallion com trigger automatico do Observer.

Pipeline puro de dados: Pre-Check > Bronze > Silver > Gold > Validation.
O Observer Agent continua separado e eh disparado automaticamente por uma task
sentinel (`observer_trigger`) quando houver falha real no workflow.

Overwrite idempotente em cada camada — nao ha rollback Delta, em caso de falha
o Observer entra em acao para diagnosticar e propor correcao via PR no GitHub.

Uso: python deploy/create_workflow.py

Requer env vars: DATABRICKS_HOST, DATABRICKS_TOKEN
Opcionais: PIPELINE_CLUSTER_ID, PIPELINE_ADMIN_EMAIL, PIPELINE_CATALOG,
           PIPELINE_SECRET_SCOPE, OBSERVER_JOB_ID, OBSERVER_JOB_NAME
"""

import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import (
    CronSchedule,
    JobEmailNotifications,
    JobSettings,
    NotebookTask,
    RunIf,
    Task,
    TaskDependency,
)

ADMIN_EMAIL = os.environ.get(
    "PIPELINE_ADMIN_EMAIL", "administrator@idlehub.com.br"
)
CATALOG = os.environ.get("PIPELINE_CATALOG", "medallion")
SECRET_SCOPE = os.environ.get("PIPELINE_SECRET_SCOPE", "medallion-pipeline")
CLUSTER_ID = os.environ.get("PIPELINE_CLUSTER_ID", "")
OBSERVER_JOB_ID = os.environ.get("OBSERVER_JOB_ID", "").strip()
OBSERVER_JOB_NAME = os.environ.get("OBSERVER_JOB_NAME", "workflow_observer_agent").strip()
WORKFLOW_NAME = "medallion_pipeline_whatsapp"


def find_latest_job_id(workspace: WorkspaceClient, name: str) -> int | None:
    """Retorna o job_id mais alto para um dado nome."""
    jobs = list(workspace.jobs.list(name=name))
    if not jobs:
        return None
    return max(int(job.job_id) for job in jobs if getattr(job, "job_id", None) is not None)


def resolve_observer_job_id(workspace: WorkspaceClient) -> str:
    """Resolve o job do Observer via env var ou lookup pelo nome padrao."""
    if OBSERVER_JOB_ID:
        return OBSERVER_JOB_ID

    existing_job_id = find_latest_job_id(workspace, OBSERVER_JOB_NAME)
    if existing_job_id is not None:
        return str(existing_job_id)

    raise RuntimeError(
        "Observer job nao encontrado. Defina OBSERVER_JOB_ID ou crie o "
        f"workflow '{OBSERVER_JOB_NAME}' antes de criar o ETL."
    )


def create_workflow():
    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    user = w.current_user.me()
    print(f"Conectado como: {user.user_name}")

    # Path do Databricks Repo — o mesmo repo hospeda tanto o pipeline
    # (pipelines/pipeline-seguradora-whatsapp/) quanto o observer framework
    # (observer-framework/). A task sentinel referencia o notebook do
    # framework via path absoluto, sem import Python.
    repo_base = f"/Repos/{user.user_name}/agentic-workflow-medallion-pipeline"
    pipeline_path = f"{repo_base}/pipelines/pipeline-seguradora-whatsapp"
    observer_framework_path = f"{repo_base}/observer-framework"

    def nb(name: str) -> str:
        return f"{pipeline_path}/notebooks/{name}"

    def observer_nb(name: str) -> str:
        return f"{observer_framework_path}/notebooks/{name}"

    shared_params = {
        "catalog": CATALOG,
        "scope": SECRET_SCOPE,
        "chaos_mode": "off",
    }
    observer_job_id = resolve_observer_job_id(w)

    cluster_kwargs = {}
    if CLUSTER_ID:
        cluster_kwargs["existing_cluster_id"] = CLUSTER_ID
        print(f"  Cluster: {CLUSTER_ID}")
    else:
        print("  Compute: serverless")

    core_dependencies = [
        "pre_check",
        "bronze_ingestion",
        "silver_dedup",
        "silver_entities",
        "silver_enrichment",
        "gold_analytics",
        "quality_validation",
    ]

    tasks = [
        Task(
            task_key="pre_check",
            description="Pre-flight check: propaga run_id e chaos_mode",
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("pre_check"),
                base_parameters={
                    **shared_params,
                    "bronze_prefix": "bronze/",
                },
            ),
            max_retries=1,
            timeout_seconds=900,
        ),
        Task(
            task_key="bronze_ingestion",
            description="S3 parquet -> Delta bronze.conversations",
            depends_on=[
                TaskDependency(task_key="pre_check"),
            ],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("bronze/ingest"),
                base_parameters={
                    **shared_params,
                    "bronze_prefix": "bronze/",
                },
            ),
            max_retries=2,
            timeout_seconds=900,
        ),
        Task(
            task_key="silver_dedup",
            description="Dedup sent+delivered, normaliza nomes",
            depends_on=[
                TaskDependency(task_key="bronze_ingestion"),
            ],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("silver/dedup_clean"),
                base_parameters=shared_params,
            ),
            max_retries=2,
            timeout_seconds=600,
        ),
        Task(
            task_key="silver_entities",
            description="Entity extraction + masking + redaction",
            depends_on=[
                TaskDependency(task_key="silver_dedup"),
            ],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("silver/entities_mask"),
                base_parameters=shared_params,
            ),
            max_retries=2,
            timeout_seconds=900,
        ),
        Task(
            task_key="silver_enrichment",
            description="Metricas por conversa",
            depends_on=[
                TaskDependency(task_key="silver_dedup"),
            ],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("silver/enrichment"),
                base_parameters=shared_params,
            ),
            max_retries=2,
            timeout_seconds=600,
        ),
        Task(
            task_key="gold_analytics",
            description="12 notebooks analiticos",
            depends_on=[
                TaskDependency(task_key="silver_entities"),
                TaskDependency(task_key="silver_enrichment"),
            ],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("gold/analytics"),
                base_parameters=shared_params,
            ),
            max_retries=1,
            timeout_seconds=1800,
        ),
        Task(
            task_key="quality_validation",
            description="Row counts, null rates, consistency",
            depends_on=[
                TaskDependency(task_key="gold_analytics"),
            ],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("validation/checks"),
                base_parameters=shared_params,
            ),
            max_retries=1,
            timeout_seconds=300,
        ),
        Task(
            task_key="observer_trigger",
            description="Dispara o workflow_observer_agent apos falha real no ETL",
            depends_on=[
                TaskDependency(task_key=task_key) for task_key in core_dependencies
            ],
            run_if=RunIf.AT_LEAST_ONE_FAILED,
            **cluster_kwargs,
            notebook_task=NotebookTask(
                # Notebook vive no observer-framework (framework desacoplado).
                # O pipeline so referencia via path — zero import Python.
                notebook_path=observer_nb("trigger_sentinel"),
                base_parameters={
                    "catalog": CATALOG,
                    "scope": SECRET_SCOPE,
                    "observer_job_id": observer_job_id,
                    "llm_provider": "anthropic",
                    "git_provider": "github",
                    # Path absoluto do observer_config.yaml deste pipeline,
                    # repassado pelo sentinel ao Observer via notebook_params.
                    "observer_config_path": (
                        f"/Workspace{pipeline_path}/observer_config.yaml"
                    ),
                },
            ),
            max_retries=0,
            timeout_seconds=300,
        ),
    ]

    job_settings = JobSettings(
        name=WORKFLOW_NAME,
        description=(
            "Pipeline ETL Medallion: Pre-Check > Bronze > Silver > Gold > Validation.\n"
            "Overwrite idempotente em cada camada. Sem rollback Delta.\n"
            "Observer Agent disparado automaticamente por task sentinel em caso de falha."
        ),
        tasks=tasks,
        tags={
            "Project": "medallion-pipeline",
            "Team": "data-engineering",
            "CostCenter": "pipeline-001",
            "Environment": "production",
            "Type": "etl-pipeline",
        },
        schedule=CronSchedule(
            quartz_cron_expression="0 0 6 * * ?",
            timezone_id="America/Sao_Paulo",
        ),
        max_concurrent_runs=1,
        timeout_seconds=3600,
        email_notifications=JobEmailNotifications(
            on_failure=[ADMIN_EMAIL],
            on_start=[ADMIN_EMAIL],
        ),
    )

    existing_job_id = find_latest_job_id(w, WORKFLOW_NAME)
    if existing_job_id is not None:
        w.jobs.reset(job_id=existing_job_id, new_settings=job_settings)
        job_id = existing_job_id
        action = "Workflow atualizado"
    else:
        job = w.jobs.create(**job_settings.as_dict())
        job_id = job.job_id
        action = "Workflow criado"

    print(f"{action}!")
    print(f"  Job ID:   {job_id}")
    print(f"  Nome:     {WORKFLOW_NAME}")
    print(f"  Tasks:    {len(tasks)}")
    print(f"  Observer: {observer_job_id}")
    print(f"  Admin:    {ADMIN_EMAIL}")

    return job_id


if __name__ == "__main__":
    job_id = create_workflow()
    print(f"\nPara executar: python deploy/trigger_run.py {job_id}")
