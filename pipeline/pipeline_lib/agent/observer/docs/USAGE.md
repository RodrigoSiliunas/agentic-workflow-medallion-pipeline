# Usage

Exemplos práticos de como usar o Observer Agent em diferentes cenários.

## Cenário 1: Fluxo padrão (pipeline → observer → PR)

### Setup do pipeline monitorado

Adicione uma task sentinel ao seu workflow ETL:

```python
# deploy/create_workflow.py
from databricks.sdk.service.jobs import RunIf, Task, TaskDependency, NotebookTask

tasks = [
    # ... suas tasks ETL normais ...
    Task(
        task_key="observer_trigger",
        description="Dispara o workflow_observer_agent em caso de falha real",
        depends_on=[
            TaskDependency(task_key="task_1"),
            TaskDependency(task_key="task_2"),
            # ... todas as tasks que você quer monitorar
        ],
        run_if=RunIf.AT_LEAST_ONE_FAILED,  # <-- chave da mágica
        existing_cluster_id=CLUSTER_ID,
        notebook_task=NotebookTask(
            notebook_path=f"{repo_path}/notebooks/observer/trigger_sentinel",
            base_parameters={
                "catalog": "medallion",
                "scope": "medallion-pipeline",
                "observer_job_id": str(OBSERVER_JOB_ID),
                "llm_provider": "anthropic",
                "git_provider": "github",
            },
        ),
        max_retries=0,
        timeout_seconds=300,
    ),
]
```

Quando qualquer task upstream falhar, o sentinel roda, identifica as falhas reais (ignorando `UPSTREAM_FAILED` em cascata) e dispara o Observer job automaticamente.

### Setup do Observer job

```python
# deploy/create_observer_workflow.py
from databricks.sdk.service.jobs import JobSettings, NotebookTask, Task

job_settings = JobSettings(
    name="workflow_observer_agent",
    description="Agente AI autonomo — triggered por pipelines que falharam",
    tasks=[
        Task(
            task_key="observe_and_fix",
            existing_cluster_id=CLUSTER_ID,
            notebook_task=NotebookTask(
                notebook_path=f"{repo_path}/notebooks/observer/collect_and_fix",
                base_parameters={
                    "catalog": "medallion",
                    "scope": "medallion-pipeline",
                    "source_run_id": "",      # preenchido pelo sentinel
                    "source_job_id": "",
                    "source_job_name": "",
                    "failed_tasks": "[]",
                    "llm_provider": "",        # vazio = usa YAML
                    "git_provider": "",
                    "dedup_window_hours": "",
                    "dry_run": "false",
                },
            ),
            timeout_seconds=900,
        ),
    ],
    max_concurrent_runs=3,
)
```

Pronto. A partir daqui, qualquer falha no pipeline monitorado dispara o Observer.

---

## Cenário 2: Disparo manual para debug

Se você já tem um run que falhou e quer rodar o Observer contra ele sem esperar o próximo run do pipeline:

```python
from databricks.sdk import WorkspaceClient
import os

w = WorkspaceClient(
    host=os.environ["DATABRICKS_HOST"],
    token=os.environ["DATABRICKS_TOKEN"],
)

run = w.jobs.run_now(
    job_id=OBSERVER_JOB_ID,
    notebook_params={
        "source_run_id": "123456789",
        "source_job_id": "987654321",
        "source_job_name": "my_pipeline",
        "failed_tasks": '["bronze_ingestion"]',
    },
)
print(f"Observer disparado: {run.run_id}")
```

---

## Cenário 3: Dry-run (diagnóstico sem criar PR)

Útil para validar setup em staging ou testar prompts novos:

```python
run = w.jobs.run_now(
    job_id=OBSERVER_JOB_ID,
    notebook_params={
        "source_run_id": "123456789",
        "dry_run": "true",
        "dedup_window_hours": "0",  # força cache miss para garantir diagnóstico
    },
)
```

O Observer vai:
1. Chamar o LLM normalmente
2. Validar sintaxe do fix
3. **Não criar PR**
4. Persistir o registro com `status='dry_run'`
5. Logar o preview do fix no output do notebook

Você pode revisar o `diagnosis`, `root_cause`, `fixed_code` na tabela sem abrir PRs reais.

---

## Cenário 4: Diferentes modelos por execução

Sobrescreve o config YAML via widget apenas para esse run:

```python
run = w.jobs.run_now(
    job_id=OBSERVER_JOB_ID,
    notebook_params={
        "source_run_id": "123456789",
        "llm_provider": "openai",          # troca de Anthropic para OpenAI
        "git_provider": "github",          # mantém default
    },
)
```

Widgets vazios são ignorados (preservam o YAML). Widgets preenchidos sobrescrevem.

---

## Cenário 5: Forçar re-diagnóstico (ignorar dedup)

```python
run = w.jobs.run_now(
    job_id=OBSERVER_JOB_ID,
    notebook_params={
        "source_run_id": "123456789",
        "dedup_window_hours": "0",  # janela = 0h → nada é considerado recente
    },
)
```

---

## Cenário 6: Usando programaticamente (sem Databricks job)

Se você quer chamar o Observer como biblioteca Python pura:

```python
from databricks.sdk import WorkspaceClient
from pipeline_lib.agent.observer import (
    ObserverDiagnosticsStore,
    WorkflowObserver,
    check_duplicate,
    load_observer_config,
    validate_fix,
)
from pipeline_lib.agent.observer.providers import (
    DiagnosisRequest,
    create_git_provider,
    create_llm_provider,
)

def diagnose_and_fix(run_id: int, spark):
    config = load_observer_config("observer_config.yaml")

    llm = create_llm_provider(
        config.llm_provider,
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model=config.llm_model,
        max_tokens=config.llm_max_tokens,
    )
    git = create_git_provider(
        config.git_provider,
        token=os.environ["GITHUB_TOKEN"],
        repo=os.environ["GITHUB_REPO"],
        base_branch=config.base_branch,
    )

    w = WorkspaceClient()
    observer = WorkflowObserver(w)
    failure = observer.build_failure_from_run(run_id=run_id)
    ctx = observer.build_context(failure, catalog="medallion")

    store = ObserverDiagnosticsStore(spark, catalog="medallion")
    store.ensure_schema()

    # Dedup
    dup = check_duplicate(
        store, ctx["error_message"],
        window_hours=config.dedup_window_hours,
        git_provider=git,
    )
    if dup.is_duplicate:
        return {"skipped": True, "reason": dup.reason}

    # Diagnóstico
    req = DiagnosisRequest(
        error_message=ctx["error_message"],
        stack_trace=ctx["error_message"],
        failed_task=ctx["failed_task"],
        notebook_code=ctx["notebook_code"],
        schema_info=ctx["schema_info"],
        pipeline_state=ctx["pipeline_state"],
    )
    diagnosis = llm.diagnose(req)

    # Validação
    for fix in diagnosis.normalized_fixes():
        result = validate_fix(fix["code"], fix["file_path"])
        if not result.valid:
            return {"skipped": True, "reason": "validation_failed", "errors": result.errors}

    # PR
    if config.dry_run:
        return {"dry_run": True, "confidence": diagnosis.confidence}

    pr = git.create_fix_pr(diagnosis, ctx["failed_task"])
    return {"pr_url": pr.pr_url, "confidence": diagnosis.confidence}
```

---

## Cenário 7: Consultando métricas do dashboard

```sql
-- Quanto o Observer gastou hoje?
SELECT ROUND(SUM(estimated_cost_usd), 4) AS custo_hoje_usd
FROM medallion.observer.diagnostics
WHERE DATE(timestamp) = CURRENT_DATE();

-- Qual a taxa de merge dos PRs do Observer?
SELECT
    COUNT(*) AS total_prs,
    SUM(CASE WHEN feedback = 'fix_accepted' THEN 1 ELSE 0 END) AS merged,
    ROUND(
        SUM(CASE WHEN feedback = 'fix_accepted' THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(*), 0),
        2
    ) AS taxa_merge_pct
FROM medallion.observer.diagnostics
WHERE status = 'success' AND pr_number > 0;

-- Quais erros aparecem mais frequentemente?
SELECT
    error_hash,
    SUBSTRING(error_message, 1, 80) AS erro_resumo,
    COUNT(*) AS ocorrencias
FROM medallion.observer.diagnostics
GROUP BY error_hash, SUBSTRING(error_message, 1, 80)
ORDER BY ocorrencias DESC
LIMIT 10;
```

Mais queries em `deploy/dashboard_queries.sql`.

---

## Chaos testing

O Observer foi desenvolvido com injeção controlada de falhas para validar o fluxo completo end-to-end:

```bash
# Dispara o pipeline com chaos mode ativo
python pipeline/deploy/trigger_chaos.py bronze_schema
python pipeline/deploy/trigger_chaos.py silver_null
python pipeline/deploy/trigger_chaos.py gold_divide_zero
python pipeline/deploy/trigger_chaos.py validation_strict
```

Cada modo injeta um tipo diferente de falha:
- `bronze_schema`: coluna inválida no DataFrame que quebra validação
- `silver_null`: NULLs em `conversation_id` que quebram dedup/groupBy
- `gold_divide_zero`: `F.lit(1) / F.lit(0)` que gera ArithmeticException
- `validation_strict`: threshold impossível no quality check

O fluxo esperado: task falha → sentinel dispara Observer → Observer gera fix → PR criado no GitHub.
