# Architecture

Este documento descreve as decisões de design do Observer Agent, a estrutura interna dos módulos e os contratos entre componentes.

## Princípios

1. **Workflow-agnostic.** O Observer não deve conhecer nada específico de um pipeline. Ele recebe um `run_id`, consulta as APIs do Databricks e age.
2. **Providers plugáveis.** LLM e Git são pontos de variação. Adicionar um provider novo não deve requerer mudanças no core.
3. **Falhas não-críticas são isoladas.** Dedup, persistência, observabilidade são diferenciais — se qualquer uma falhar, o fluxo principal (diagnosticar e criar PR) segue.
4. **Safe defaults.** Em caso de ambiguidade (PR status desconhecido, query falhando), o sistema prefere o comportamento mais conservador — skip em vez de duplicar.
5. **Retrocompatibilidade.** Mudanças no `DiagnosisResult` mantêm o formato antigo funcionando via fallback.

---

## Diagrama de camadas

```
┌─────────────────────────────────────────────────────────┐
│  Notebook / CLI                                         │
│  collect_and_fix.py  |  update_pr_feedback.py           │
└────────────────────┬────────────────────────────────────┘
                     │
     ┌───────────────┼────────────────────────────┐
     │               │                            │
     ▼               ▼                            ▼
┌─────────────┐  ┌──────────┐  ┌────────────────────────┐
│ config.py   │  │ dedup.py │  │ workflow_observer.py   │
│ (YAML +     │  │ (cache)  │  │ (Databricks APIs)       │
│  widgets)   │  │          │  │                         │
└─────────────┘  └────┬─────┘  └────────────┬───────────┘
                      │                     │
                      ▼                     ▼
           ┌──────────────────┐  ┌──────────────────────┐
           │ persistence.py   │  │ providers/           │
           │ (Delta store)    │  │                      │
           │                  │  │ ┌──────────────────┐ │
           │ - ensure_schema  │  │ │ base.py (ABCs)   │ │
           │ - save           │  │ ├──────────────────┤ │
           │ - find_recent    │  │ │ anthropic_prov   │ │
           │ - update_pr_fdbk │  │ │ openai_provider  │ │
           │ - _migrate_cols  │  │ │ github_provider  │ │
           └──────────────────┘  │ └──────────────────┘ │
                                 └──────────────────────┘
                                              │
                                              ▼
                                      validator.py
                                      (compile + ruff)
```

---

## Responsabilidade de cada módulo

### `workflow_observer.py`

Camada de acesso às APIs do Databricks. **Não conhece LLMs nem Git.** Só sabe buscar dados.

Responsabilidades:
- `find_recent_failures(hours, workflow_name)`: lista runs com falha via Jobs API
- `build_failure_from_run(run_id, job_id, job_name, failed_tasks_hint)`: monta dict de falha a partir do estado do run
- `collect_notebook_code(run_id)`: lê código fonte de cada notebook via Workspace API + base64 decode
- `collect_schema_info(catalog, schemas)`: lista tabelas e colunas via Unity Catalog
- `build_context(failure, catalog)`: orquestra os passos anteriores e monta o dict que será enviado ao LLM

### `triggering.py`

Helpers para o task sentinel. Vive separado de `workflow_observer.py` porque o sentinel roda em contexto diferente (uma task leve, não o job do Observer inteiro).

Responsabilidades:
- `extract_failed_task_keys(tasks)`: filtra tasks com falha real, ignorando `UPSTREAM_FAILED` em cascata
- `is_root_failure_state(state)`: identifica FAILED/TIMEDOUT/INTERNAL_ERROR/CANCELED, exclui cascades
- `build_observer_notebook_params(...)`: serializa metadata para passar ao Observer via `notebook_params`
- `resolve_runtime_context(tags, current_run_id)`: descobre o parent run do multitask job a partir das tags do Databricks notebook context
- `parse_failed_tasks_param(value)`: aceita JSON ou lista CSV vinda de widgets

### `config.py`

Camada de configuração tipada.

Responsabilidades:
- `ObserverConfig` (Pydantic BaseModel): 10 campos validados
- `load_observer_config(config_path, overrides)`: combina YAML + widgets + defaults na hierarquia correta
- `_coerce_override_value(field, value)`: converte strings de widgets para tipos certos
- `_coerce_bool(value)`: helper compartilhado para aceitar "true"/"yes"/"1"/"on"
- `_read_config_file(path)`: suporta YAML e JSON, flat ou com seção `observer:`

**Compat Pydantic V1/V2:** `class Config: extra = "forbid"` em vez de `ConfigDict`, `getattr(..., "model_fields", None) or __fields__`, `_coerce_bool` em vez de `@field_validator`.

### `dedup.py`

Lógica de deduplicação de diagnósticos.

Responsabilidades:
- `check_duplicate(store, error_message, window_hours, git_provider) -> DuplicateCheckResult`: orquestra hash → query no store → check de status do PR
- `DuplicateCheckResult`: dataclass com `is_duplicate`, `reason`, `existing_record`

Fluxo:
1. Gera `error_hash` via SHA-256
2. `store.find_recent_successful(hash, window_hours)`
3. Se vazio → cache miss, permite diagnóstico
4. Se encontrou e sem git provider → safe default (skip)
5. Se encontrou e git provider disponível:
   - Consulta `git.get_pr_status(pr_number)`
   - `open`/`merged` → skip (fix ainda válido)
   - `closed` sem merge → permite re-diagnóstico (fix anterior foi rejeitado)
   - `unknown` ou exception → safe default (skip)

### `validator.py`

Validação pré-PR do código gerado pelo LLM.

Responsabilidades:
- `validate_fix(code, file_path) -> ValidationResult`
- `_check_syntax(code, file_path)`: `compile` + `ast.parse`
- `_run_ruff(code, file_path)`: subprocess com `ruff check --output-format=json`, fallback gracioso se ruff não está instalado
- `_should_run_ruff(file_path)`: decide por path (evita rodar ruff em notebooks/)
- `_parse_ruff_json(stdout)`: converte saída do ruff em mensagens legíveis

**Decisão importante:** não roda pytest. Pytest exigiria sandbox para aplicar o fix sem afetar o runtime — deixado como out-of-scope.

### `persistence.py`

Camada de persistência em Delta Lake.

Responsabilidades:
- `ObserverDiagnosticsStore`: encapsula todas as operações de read/write na tabela
  - `ensure_schema()`: cria schema + tabela + aplica migrações
  - `_migrate_columns()`: ALTER TABLE ADD COLUMNS para `MIGRATED_COLUMNS` ausentes, via `DESCRIBE TABLE`
  - `build_record(...)`: monta `DiagnosticRecord` a partir de `DiagnosisResult` + `PRResult` + metadata
  - `save(record)`: insere na tabela
  - `find_recent_successful(error_hash, window_hours)`: query para dedup
  - `update_pr_feedback(pr_number, pr_status)`: update para feedback loop
- `DiagnosticRecord`: dataclass com 28 campos
- `calculate_cost_usd(provider, model, input_tokens, output_tokens)`: lookup na `PRICING` table
- `error_hash(error_message)`: SHA-256 normalizado (strip)

### `providers/base.py`

Contratos entre o core e os providers.

Responsabilidades:
- `LLMProvider` (ABC): `diagnose(request) -> DiagnosisResult`, `name` property
- `GitProvider` (ABC): `create_fix_pr(diagnosis, failed_task) -> PRResult`, `get_pr_status(pr_number) -> str` (opcional, default `"unknown"`)
- `DiagnosisRequest` (dataclass): contexto enviado ao LLM
- `DiagnosisResult` (dataclass): resposta estruturada do LLM + método `normalized_fixes()` para unificar singular/multi-file
- `PRResult` (dataclass): retorno do `create_fix_pr`
- `@with_retry(max_retries, base_delay)`: decorator com exponential backoff, ignora erros de lógica

### `providers/__init__.py`

Factory + registry.

Responsabilidades:
- `_LLM_REGISTRY` e `_GIT_REGISTRY`: dicts nome → classe
- `register_llm_provider(name)` e `register_git_provider(name)`: decorators
- `create_llm_provider(name, **kwargs)` e `create_git_provider(name, **kwargs)`: factories
- Lazy imports de providers específicos com `contextlib.suppress(ImportError)` — dependências opcionais

### Providers concretos

- `anthropic_provider.py`: Claude API via `anthropic` SDK. Streaming obrigatório para `max_tokens > 8192`.
- `openai_provider.py`: OpenAI API via `openai` SDK. Compatível com Azure OpenAI passando `base_url`.
- `github_provider.py`: PyGithub. Cria branch `fix/agent-auto-{task}-{timestamp}`, commita cada arquivo de `normalized_fixes()` individualmente, abre PR contra `base_branch` (default `dev`).

---

## Fluxo end-to-end de uma execução

### 1. Trigger

```
Pipeline ETL rodando → task X falha
  ↓
Task sentinel observer_trigger (run_if: AT_LEAST_ONE_FAILED)
  ├─ Lê tags do notebook context (multitaskParentRunId, jobId)
  ├─ extract_failed_task_keys(parent_run.tasks)
  │  └─ ['bronze_ingestion']  # só falhas reais, ignora UPSTREAM_FAILED
  └─ w.jobs.run_now(OBSERVER_JOB_ID, notebook_params={
        source_run_id, source_job_id, source_job_name, failed_tasks
     })
```

### 2. Observer job

```
collect_and_fix.py notebook
  ├─ load_observer_config(yaml + widgets)  # config com dry_run, dedup_window, etc.
  ├─ store.ensure_schema()  # cria observer.diagnostics se faltar, migra colunas
  ├─ observer.build_failure_from_run(source_run_id)  # failed_tasks + errors
  ├─ observer.build_context(failure)
  │  ├─ collect_notebook_code (Workspace API)
  │  ├─ collect_schema_info (Unity Catalog)
  │  └─ monta dict com error_message, notebook_code, schema_info, pipeline_state
  │
  ├─ check_duplicate(store, error_message, window_hours, git)
  │  ├─ error_hash (SHA-256)
  │  ├─ store.find_recent_successful(hash, window)
  │  ├─ [se encontrou] git.get_pr_status(pr_number)
  │  └─ retorna DuplicateCheckResult
  │
  ├─ [se duplicate]
  │   └─ store.save(status='duplicate_skip') e encerra
  │
  ├─ [se cache miss]
  │  └─ llm.diagnose(DiagnosisRequest)
  │      ├─ Anthropic streaming / OpenAI chat.completions
  │      └─ retorna DiagnosisResult (com fixes singular ou lista)
  │
  ├─ diagnosis.normalized_fixes() → [{file_path, code}, ...]
  │
  ├─ [se lista vazia]    → status='no_fix_proposed'
  ├─ [se confidence < threshold] → status='low_confidence'
  ├─ [else]
  │   └─ for each fix:
  │       validate_fix(code, file_path)
  │       ├─ compile + ast.parse
  │       └─ ruff check (se nao for notebook)
  │
  ├─ [se algum falhou] → status='validation_failed'
  ├─ [se dry_run]      → status='dry_run'
  ├─ [else]
  │   └─ git.create_fix_pr(diagnosis, failed_task)
  │       ├─ cria branch
  │       ├─ commit por arquivo
  │       ├─ cria PR
  │       └─ retorna PRResult
  │       status='success' ou 'pr_failed' se deu exception
  │
  └─ store.save(DiagnosticRecord com status final)
```

### 3. Feedback loop (async, depois que humano interage com o PR)

```
Humano merge/fecha o PR
  ↓
GitHub Action observer-feedback.yml
  ├─ if: startsWith(head_ref, 'fix/agent-auto-')
  ├─ determina status (merged/closed) via pr.merged
  └─ python update_pr_feedback.py --pr-number X --status Y
     └─ UPDATE observer.diagnostics
        SET pr_status, pr_resolved_at, resolution_time_hours, feedback
        WHERE pr_number = X
```

---

## Contratos externos

### LLM (providers)

O LLM deve retornar JSON estruturado. Formato esperado:

```json
{
    "diagnosis": "texto do diagnostico",
    "root_cause": "causa raiz",
    "fix_description": "descricao do fix",
    "confidence": 0.85,
    "requires_human_review": false,
    "additional_notes": "observacoes",

    // Formato singular:
    "fixed_code": "codigo completo do arquivo",
    "file_to_fix": "pipeline/notebooks/bronze/ingest.py"

    // OU formato multi-file:
    // "fixes": [
    //     {"file_path": "a.py", "code": "..."},
    //     {"file_path": "b.py", "code": "..."}
    // ]
}
```

O parser aceita também respostas dentro de code blocks Markdown (```json ... ```) como fallback.

### Git (providers)

Operações obrigatórias:
- `create_fix_pr(diagnosis, failed_task) -> PRResult`

Operações opcionais (com default `"unknown"` no ABC):
- `get_pr_status(pr_number) -> str`: retorna `"open"`, `"merged"`, `"closed"` ou `"unknown"`

Convenções:
- Branches: `fix/agent-auto-{task_slug}-{timestamp}` onde `task_slug` é `failed_task.replace('_', '-')` e `timestamp` é `YYYYMMDD-HHMMSS`
- PR title: `fix: [{failed_task}] correcao automatica[ ({N} arquivos)]`
- PR body: diagnóstico, causa raiz, fix description, arquivos modificados, crédito ao LLM usado

### Tabela Delta `observer.diagnostics`

Ver README principal para o schema completo. Campos principais:
- **Identificação:** `id`, `timestamp`, `job_id`, `job_name`, `run_id`, `failed_task`
- **Erro:** `error_message`, `error_hash`
- **Diagnóstico:** `diagnosis`, `root_cause`, `fix_description`, `file_to_fix`, `confidence`, `requires_human_review`
- **PR:** `pr_url`, `pr_number`, `branch_name`, `pr_status`, `pr_resolved_at`, `resolution_time_hours`, `feedback`
- **Provider:** `provider`, `model`, `input_tokens`, `output_tokens`, `estimated_cost_usd`
- **Operacional:** `duration_seconds`, `status`

Status possíveis:
- `success` — PR criado
- `duplicate_skip` — dedup marcou como já diagnosticado
- `no_fix_proposed` — LLM respondeu mas sem fix
- `low_confidence` — LLM abaixo do `confidence_threshold`
- `validation_failed` — fix rejeitado pelo validator
- `dry_run` — modo dry-run ativo
- `pr_failed` — exception ao criar PR
- `llm_failed` — exception ao chamar o LLM

---

## Decisões por quê

### Por que factory + registry em vez de subclassing direto?

Permite adicionar providers novos sem tocar no código do consumidor. O notebook só precisa de `create_llm_provider(config.llm_provider)`. A string vem do YAML, o decorator `@register_llm_provider("nome")` no módulo do provider novo é descoberto via lazy import.

### Por que `with_retry` ignora `ValueError`, `KeyError`, `TypeError`?

Esses são erros de lógica — retentar não vai ajudar. Só erros transientes (network, rate limit, timeout) merecem retry com backoff.

### Por que commits separados no multi-file em vez de um commit único?

Mais simples com PyGithub (que tem `update_file`/`create_file` para operações atômicas). O PR final mostra todas as mudanças agregadas e o diff fica legível. Se um dos arquivos falhar ao commitar, a branch fica parcial mas a exception propaga e o fluxo marca `status='pr_failed'`.

### Por que pytest ficou fora do validator?

Pytest precisa aplicar o fix temporariamente no disco para rodar os testes. Isso exige sandbox isolado para não afetar outros processos no mesmo cluster. Complexidade grande demais para o ganho marginal — `compile` + `ruff` já pegam 90% dos casos de fix quebrado.

### Por que a tabela está em `{catalog}.observer.diagnostics` e não `{catalog}.pipeline.observer_diagnostics`?

Schema dedicado dá isolamento de permissions (quem precisa ler metrics do agente não precisa ver tabelas de pipeline) e evita conflito de nomes quando múltiplos Observers rodam em workspaces compartilhados.

### Por que `safe default = skip` no dedup quando o status é unknown?

PRs duplicados são barulhentos e caros. Perder um diagnóstico ocasional porque o status do PR estava indeterminado é um custo menor. Se isso for um problema, o usuário pode ajustar `dedup_window_hours=0` para forçar cache miss.
