# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Unreleased]

Nada pendente neste momento.

## [0.8.0] — 2026-04-10

### Added — Feedback loop (track 8/8)

- `ObserverDiagnosticsStore.update_pr_feedback(pr_number, pr_status)`: atualiza `pr_status`, `pr_resolved_at`, `resolution_time_hours` e `feedback` na tabela de diagnósticos
- 4 campos novos em `observer.diagnostics`: `pr_status`, `pr_resolved_at`, `resolution_time_hours`, `feedback`
- `_migrate_columns()` idempotente que aplica `ALTER TABLE ADD COLUMNS` em tabelas existentes via `DESCRIBE TABLE`
- Script CLI `deploy/update_pr_feedback.py` chamado pela GitHub Action
- GitHub Action `.github/workflows/observer-feedback.yml` triggered em `pull_request.closed` com filtro de branch `fix/agent-auto-*`
- 3 painéis novos no dashboard SQL: taxa de aceitação, tempo médio de resolução, eficácia por provider

### Fixed

- `wait_timeout="60s"` no `statement_execution` retornava `InvalidParameterValue` — limite máximo do Databricks é 50s

## [0.7.0] — 2026-04-10

### Added — Multi-file fixes (track 7/8)

- Campo opcional `fixes: list[dict] | None` em `DiagnosisResult`
- Método `DiagnosisResult.normalized_fixes()` unifica formato singular (`fixed_code`/`file_to_fix`) e lista (`fixes`) com fallback automático
- `GitHubProvider.create_fix_pr()` itera sobre `normalized_fixes()` criando um commit por arquivo na mesma branch
- PR title mostra contagem de arquivos quando > 1; body lista todos os arquivos modificados
- `SYSTEM_PROMPT` atualizado para instruir o LLM sobre quando usar singular vs multi-file
- Validação pré-PR roda para cada arquivo proposto; qualquer falha rejeita o fix inteiro

### Validated in production

- Run `101976244935180`: LLM gerou fix com `SyntaxError (linha 185): ':' expected after dictionary key`. Validator rejeitou antes de criar PR no GitHub. **Primeira rejeição real de um fix quebrado evitou PR quebrado na prática.**

## [0.6.0] — 2026-04-10

### Added — Validação pré-PR (track 6/8)

- `validate_fix(code, file_path) -> ValidationResult`
- Check 1 (sempre): `compile()` + `ast.parse()` para detectar erros sintáticos. Notebooks Databricks com magics (`# MAGIC`, `# COMMAND`) passam porque são comentários do ponto de vista do parser Python
- Check 2 (condicional): `ruff check --output-format=json` via subprocess, apenas para arquivos fora de `notebooks/` (consistente com `pyproject.toml` que exclui notebooks do lint)
- Graceful skip quando `ruff` não está instalado (`_run_ruff` retorna None)
- Novo status `validation_failed` persistido na tabela

### Not implemented (deferred)

- Pytest pré-PR: requer sandbox isolado do `pipeline_lib` para aplicar o fix sem afetar o runtime

## [0.5.0] — 2026-04-10

### Added — Config como código (track 5/8)

- `ObserverConfig` (Pydantic) com 10 campos tipados: `llm_provider`, `llm_model`, `llm_max_tokens`, `git_provider`, `base_branch`, `max_retries`, `dedup_window_hours`, `dry_run`, `confidence_threshold`, `max_tokens_per_day`
- `load_observer_config()` combina YAML/JSON do repo com overrides de widgets
- Hierarquia de prioridade: widgets > YAML > defaults
- `observer_config.yaml` documentado no repo
- `_coerce_override_value` normaliza strings de widgets para tipos corretos (int/float/bool) com fallback silencioso
- Novo check de `confidence_threshold` no notebook: se abaixo do limite, marca `status='low_confidence'` sem criar PR

### Fixed

- Compat Pydantic V1 (Databricks Runtime) e V2 (dev local): `class Config` V1-style, `_coerce_bool` helper no lugar de `@field_validator`, `getattr(ObserverConfig, "model_fields", None) or __fields__`

## [0.4.0] — 2026-04-10

### Added — Modo dry-run (track 4/8)

- Widget `dry_run` (dropdown `false`/`true`) no notebook do Observer
- Quando ativo, LLM é chamado normalmente (diagnóstico + tokens contabilizados) mas `create_fix_pr` **não** é executado
- Preview do fix e root cause logados no output
- Novo status `dry_run` persistido na tabela

## [0.3.0] — 2026-04-10

### Added — Deduplicação (track 3/8)

- `check_duplicate(store, error_message, window_hours, git_provider) -> DuplicateCheckResult`
- `ObserverDiagnosticsStore.find_recent_successful()` com query parametrizada + validação de formato SHA-256
- `GitProvider.get_pr_status(pr_number) -> str` opcional na ABC com default `"unknown"`
- `GitHubProvider.get_pr_status` via PyGithub (retorna `open` / `merged` / `closed` / `unknown`)
- Safe defaults: em caso de erro ou status desconhecido, marca como duplicate (evita PRs duplicados)
- Novo status `duplicate_skip` persistido na tabela para métricas

## [0.2.0] — 2026-04-10

### Added — Observabilidade (track 2/8)

- `ObserverDiagnosticsStore` com `ensure_schema()`, `build_record()`, `save()`
- Tabela Delta `{catalog}.observer.diagnostics` com 24 campos (ampliada para 28 na track 8)
- `calculate_cost_usd(provider, model, input_tokens, output_tokens)` com tabela `PRICING` (Anthropic Opus/Sonnet/Haiku, OpenAI GPT-4o/Turbo/4/3.5)
- `error_hash(error_message)` via SHA-256 (base para dedup)
- `DiagnosticRecord` dataclass
- 8 painéis SQL + 3 alerts em `dashboard_queries.sql`

### Fixed

- DDL usando `INT` → Spark infere `int` Python como `BIGINT`, causando `DELTA_FAILED_TO_MERGE_FIELDS`. Troca para `BIGINT` em `pr_number`, `input_tokens`, `output_tokens`

## [0.1.0] — 2026-04-10

### Added — Trigger automático + framework base (track 1/8)

- `WorkflowObserver` genérico: `find_recent_failures`, `build_failure_from_run`, `collect_notebook_code` (via Workspace API), `collect_schema_info` (via Unity Catalog API auto-discover), `build_context`
- Factory + registry pattern para providers: `create_llm_provider`, `create_git_provider`, `@register_llm_provider`, `@register_git_provider`
- ABCs `LLMProvider` e `GitProvider` em `providers/base.py`
- Dataclasses `DiagnosisRequest`, `DiagnosisResult`, `PRResult`
- Decorator `@with_retry(max_retries, base_delay)` com exponential backoff
- `AnthropicProvider` (Claude Opus streaming)
- `OpenAIProvider` (GPT-4o) com suporte a Azure OpenAI via `base_url`
- `GitHubProvider` (PyGithub) cria branches `fix/agent-auto-{task}-{timestamp}`, commits, PRs com diagnóstico
- Task sentinel `observer_trigger` com `run_if: AT_LEAST_ONE_FAILED` no workflow ETL
- Helpers em `triggering.py` para detecção de falha real vs cascata (`UPSTREAM_FAILED` filtrado)
- Notebook `collect_and_fix.py` unificando todo o fluxo
- Pipeline ETL refatorado para ser puro: `agent_post` removido, `agent_pre` → `pre_check` minimalista, zero lógica de agente nos notebooks ETL

---

[Unreleased]: https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline/releases/tag/observer-v0.8.0
[0.7.0]: https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline/releases/tag/observer-v0.7.0
[0.6.0]: https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline/releases/tag/observer-v0.6.0
[0.5.0]: https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline/releases/tag/observer-v0.5.0
[0.4.0]: https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline/releases/tag/observer-v0.4.0
[0.3.0]: https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline/releases/tag/observer-v0.3.0
[0.2.0]: https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline/releases/tag/observer-v0.2.0
[0.1.0]: https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline/releases/tag/observer-v0.1.0
