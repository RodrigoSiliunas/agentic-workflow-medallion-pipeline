# Observer Agent

**Framework agnóstico de auto-diagnóstico e correção automática para workflows Databricks.**

Observer é um agente autônomo que monitora jobs Databricks, detecta falhas reais, coleta contexto completo (código fonte, erro, schema), chama um LLM para gerar um fix, valida o código, e abre um Pull Request no GitHub — tudo sem intervenção humana.

---

## Por que existe

Pipelines de dados quebram. Quando quebram às 3 da manhã, alguém precisa:

1. Acordar e logar no Databricks
2. Ler o traceback
3. Abrir o notebook que falhou
4. Entender o erro
5. Propor um fix
6. Testar a sintaxe
7. Abrir um PR

Observer faz os passos 2 a 7 automaticamente. Em segundos, você acorda com um PR no GitHub contendo o diagnóstico, a causa raiz, o código corrigido e um indicador de confiança do modelo. Revisar e dar merge leva 2 minutos.

## Features

- **Workflow-agnostic.** Funciona com qualquer job Databricks, não só pipelines Medallion.
- **Multi-provider LLM.** Anthropic Claude, OpenAI GPT via factory pattern + registry de providers. Adicionar um provider novo requer uma classe Python.
- **Multi-provider Git.** GitHub via PyGithub hoje; GitLab/Bitbucket plugáveis pela mesma interface.
- **Trigger automático.** Task sentinel no workflow com `run_if: AT_LEAST_ONE_FAILED` dispara o Observer no segundo em que o pipeline quebra.
- **Deduplicação inteligente.** Hash SHA-256 do error message + check do status do PR no GitHub. Se o erro já tem um PR aberto ou mergeado, o Observer pula (economiza tokens e evita ruído no repo).
- **Dry-run.** Diagnostica e persiste, mas não cria PR. Útil para staging e validação de setup.
- **Config como código.** `observer_config.yaml` versionado no repo. Widgets Databricks viram overrides opcionais. Hierarquia: widgets > YAML > defaults.
- **Validação pré-PR.** `compile` + `ast.parse` + `ruff check` antes de abrir PR. Fixes com syntax error são rejeitados e registrados na tabela de observabilidade.
- **Multi-file fixes.** LLM pode propor mudanças em N arquivos num único PR (útil para bugs que cruzam módulos).
- **Observabilidade.** Tabela Delta `observer.diagnostics` com 28 campos incluindo tokens, custo estimado em USD, confiança, status do PR, tempo de resolução.
- **Feedback loop.** GitHub Action atualiza o status do PR na tabela quando o PR é mergeado ou fechado. Dashboard SQL mostra taxa de aceitação por provider/modelo.

---

## Quick start

```python
from databricks.sdk import WorkspaceClient
from observer import (
    ObserverDiagnosticsStore,
    WorkflowObserver,
    check_duplicate,
    load_observer_config,
    validate_fix,
)
from observer.providers import (
    DiagnosisRequest,
    create_git_provider,
    create_llm_provider,
)

# 1. Carrega config do YAML + overrides dos widgets
config = load_observer_config(
    config_path="/Workspace/Repos/.../pipeline/observer_config.yaml",
    overrides={"dry_run": dbutils.widgets.get("dry_run")},
)

# 2. Inicializa providers via factory
llm = create_llm_provider(
    config.llm_provider,           # "anthropic" | "openai"
    api_key=os.environ["ANTHROPIC_API_KEY"],
    model=config.llm_model,
    max_tokens=config.llm_max_tokens,
)
git = create_git_provider(
    config.git_provider,           # "github"
    token=os.environ["GITHUB_TOKEN"],
    repo="owner/repo",
    base_branch=config.base_branch,
)

# 3. Coleta contexto do run que falhou
w = WorkspaceClient()
observer = WorkflowObserver(w)
failure = observer.build_failure_from_run(run_id=123456789)
context = observer.build_context(failure, catalog="medallion")

# 4. Dedup check (opcional mas recomendado)
store = ObserverDiagnosticsStore(spark, catalog="medallion")
store.ensure_schema()

dup = check_duplicate(
    store,
    context["error_message"],
    window_hours=config.dedup_window_hours,
    git_provider=git,
)
if dup.is_duplicate:
    print(f"Cache hit: {dup.reason}")
    return

# 5. Diagnóstico via LLM
request = DiagnosisRequest(
    error_message=context["error_message"],
    stack_trace=context["error_message"],
    failed_task=context["failed_task"],
    notebook_code=context["notebook_code"],
    schema_info=context["schema_info"],
    pipeline_state=context["pipeline_state"],
)
diagnosis = llm.diagnose(request)

# 6. Validação pré-PR
for fix in diagnosis.normalized_fixes():
    result = validate_fix(fix["code"], fix["file_path"])
    if not result.valid:
        print(f"Fix rejeitado: {result.errors}")
        return

# 7. Cria PR (se não for dry-run)
if not config.dry_run:
    pr = git.create_fix_pr(diagnosis, context["failed_task"])
    print(f"PR aberto: {pr.pr_url}")
```

Para integração mais simples, o notebook `observer/collect_and_fix.py` no repositório principal já faz todo esse fluxo. Basta disparar o job do Observer passando `source_run_id` do run que falhou.

---

## Arquitetura

```
┌─────────────────────┐
│  Databricks Job X   │
│   (pipeline ETL)    │
└──────────┬──────────┘
           │ falha
           ▼
┌─────────────────────┐
│  Task sentinel       │  run_if: AT_LEAST_ONE_FAILED
│  observer_trigger    │  dispara o Observer com source_run_id
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│  Observer Job (independente)                     │
│                                                  │
│  1. WorkflowObserver.build_failure_from_run()    │
│     └─→ Jobs API (estado do run)                 │
│                                                  │
│  2. WorkflowObserver.build_context()             │
│     ├─→ Workspace API (código fonte notebook)    │
│     ├─→ Unity Catalog API (schemas)              │
│     └─→ Jobs API (task values, metadata)         │
│                                                  │
│  3. ObserverConfig.load()                        │
│     └─→ observer_config.yaml (+widgets override) │
│                                                  │
│  4. check_duplicate()                            │
│     ├─→ observer.diagnostics (query por hash)    │
│     └─→ GitProvider.get_pr_status(pr_number)     │
│                                                  │
│  5. LLMProvider.diagnose()                       │
│     └─→ Anthropic/OpenAI API                     │
│                                                  │
│  6. validate_fix()                               │
│     ├─→ compile + ast.parse                      │
│     └─→ ruff check (se nao for notebook)        │
│                                                  │
│  7. GitProvider.create_fix_pr()                  │
│     └─→ GitHub API (branch + commits + PR)       │
│                                                  │
│  8. store.save(DiagnosticRecord)                 │
│     └─→ observer.diagnostics (Delta table)       │
└─────────────────────────────────────────────────┘
                                 │
                    (tempo depois: humano merge/fecha PR)
                                 │
                                 ▼
┌─────────────────────────────────────────────────┐
│  GitHub Action observer-feedback.yml             │
│                                                  │
│  on: pull_request.closed                         │
│  if: startsWith(head_ref, 'fix/agent-auto-')     │
│                                                  │
│  └─→ update_pr_feedback.py                       │
│       └─→ UPDATE observer.diagnostics            │
│            SET pr_status, resolution_time_hours, │
│                feedback                           │
└─────────────────────────────────────────────────┘
```

### Componentes

| Módulo | Responsabilidade |
|--------|------------------|
| `workflow_observer.py` | Coleta dados do run via Databricks APIs (Jobs, Workspace, Unity Catalog) |
| `triggering.py` | Helpers do task sentinel — detecção de falha real vs cascade, build de notebook_params |
| `config.py` | `ObserverConfig` (Pydantic) + loader YAML/JSON com overrides |
| `dedup.py` | Cache check via hash SHA-256 + consulta ao Git provider |
| `validator.py` | Validação sintática + ruff antes de criar PR |
| `persistence.py` | Delta store para observabilidade + feedback loop |
| `providers/base.py` | ABCs `LLMProvider` e `GitProvider`, dataclasses `DiagnosisRequest/Result`, `PRResult`, decorator `@with_retry` |
| `providers/anthropic_provider.py` | Claude API (Opus, Sonnet, Haiku) — streaming obrigatório para max_tokens alto |
| `providers/openai_provider.py` | OpenAI API (GPT-4o, Turbo, 4, 3.5) — compatível com Azure OpenAI |
| `providers/github_provider.py` | PyGithub — cria branches `fix/agent-auto-*`, commits por arquivo, PRs com diagnóstico |

### Decisões de design

**Factory + registry.** Novos providers se registram via decorator `@register_llm_provider("nome")` e são instanciados via `create_llm_provider(nome, **kwargs)`. Zero acoplamento: o notebook do Observer não conhece provedores específicos.

**Dataclasses como contrato.** `DiagnosisRequest` e `DiagnosisResult` são o único ponto de acoplamento entre o core e os providers. Trocar de Claude para GPT não requer mudança no código que consome.

**Retry com backoff.** Decorator `@with_retry(max_retries=3, base_delay=2.0)` em todas as chamadas externas. Ignora erros de lógica (`ValueError`, `KeyError`) que não se beneficiam de retry.

**Persistência não-crítica.** O save na tabela de diagnósticos nunca bloqueia o fluxo principal — se a tabela estiver indisponível, o Observer ainda cria o PR e loga um warning. Observabilidade é diferencial, não requisito.

**Safe defaults no dedup.** Quando o status do PR é desconhecido ou a API do Git falha, o dedup assume `is_duplicate=True` (skip). Melhor perder um diagnóstico raro do que criar PRs duplicados.

---

## Providers suportados

### LLM

| Provider | Modelos | Streaming | Notas |
|----------|---------|-----------|-------|
| `anthropic` | claude-opus-4, claude-sonnet-3.5, claude-haiku | Obrigatório | `max_tokens=16000` requer streaming |
| `openai` | gpt-4o, gpt-4-turbo, gpt-4, gpt-3.5-turbo | Opcional | Compatível com Azure OpenAI via `base_url` |

Adicionar um provider novo: ver [docs/EXTENDING.md](./docs/EXTENDING.md).

### Git

| Provider | Operações | Notas |
|----------|-----------|-------|
| `github` | Create branch, commit files, create PR, get PR status | Via PyGithub; branches nomeadas `fix/agent-auto-{task}-{timestamp}` |

GitLab e Bitbucket são plugáveis via a mesma interface `GitProvider` — implementação ainda não feita.

---

## Configuração

O arquivo `observer_config.yaml` centraliza todos os parâmetros:

```yaml
observer:
  # LLM
  llm_provider: anthropic
  llm_model: claude-opus-4-20250514
  llm_max_tokens: 16000

  # Git
  git_provider: github
  base_branch: dev

  # Resilience
  max_retries: 3

  # Dedup
  dedup_window_hours: 24

  # Operacional
  dry_run: false
  confidence_threshold: 0.0
```

**Hierarquia de prioridade:**
1. Widgets Databricks (override manual — maior prioridade)
2. `observer_config.yaml`
3. Defaults hardcoded em `ObserverConfig` (menor prioridade)

Widgets vazios são ignorados (preservam o YAML). Isso permite ter um config global no repo e sobrescrever campos específicos ao disparar um run manualmente via SDK.

### Secrets

O Observer espera os seguintes secrets (via Databricks Secret Scope ou env vars):

| Key | Descrição |
|-----|-----------|
| `anthropic-api-key` | Chave da Anthropic API (se usar provider `anthropic`) |
| `openai-api-key` | Chave da OpenAI API (se usar provider `openai`) |
| `github-token` | Personal Access Token com `repo` scope |
| `github-repo` | Nome do repo (ex: `owner/repo`) |

---

## Observabilidade

A tabela `{catalog}.observer.diagnostics` (auto-criada por `ensure_schema()`) registra cada diagnóstico:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | STRING | UUID do diagnóstico |
| `timestamp` | TIMESTAMP | Quando o Observer foi acionado |
| `job_id`, `job_name`, `run_id` | BIGINT/STRING | Origem da falha |
| `failed_task` | STRING | Task que falhou no workflow |
| `error_message` | STRING | Mensagem de erro original |
| `error_hash` | STRING | SHA-256 do error_message (para dedup) |
| `diagnosis` | STRING | Diagnóstico textual do LLM |
| `root_cause` | STRING | Causa raiz identificada |
| `fix_description` | STRING | Descrição do fix proposto |
| `file_to_fix` | STRING | Arquivo modificado (primeiro em multi-file) |
| `confidence` | DOUBLE | Confiança do LLM (0.0 a 1.0) |
| `requires_human_review` | BOOLEAN | Flag de alerta do LLM |
| `pr_url`, `pr_number`, `branch_name` | STRING/BIGINT | PR criado (se houver) |
| `provider`, `model` | STRING | Qual LLM foi usado |
| `input_tokens`, `output_tokens` | BIGINT | Tokens consumidos |
| `estimated_cost_usd` | DOUBLE | Custo estimado baseado em preços públicos |
| `duration_seconds` | DOUBLE | Tempo total do diagnóstico |
| `status` | STRING | `success`, `no_fix_proposed`, `low_confidence`, `validation_failed`, `dry_run`, `duplicate_skip`, `pr_failed`, `llm_failed` |
| `pr_status` | STRING | `merged`, `closed`, ou NULL (pending) — atualizado pelo feedback loop |
| `pr_resolved_at` | TIMESTAMP | Quando o PR foi resolvido |
| `resolution_time_hours` | DOUBLE | Diff entre `timestamp` e `pr_resolved_at` |
| `feedback` | STRING | `fix_accepted` (merged) ou `fix_rejected` (closed) |

### Dashboard

`dashboard_queries.sql` traz 11 painéis prontos para o Databricks SQL:

1. Diagnósticos por dia (últimos 30 dias)
2. Custo por provider/modelo
3. Custo acumulado ao longo do tempo
4. Confiança média por task
5. Top 10 erros mais frequentes
6. Taxa de sucesso por status
7. Tempo médio de diagnóstico por provider
8. PRs criados recentemente
9. Taxa de aceitação dos fixes (feedback loop)
10. Tempo médio de resolução (merged vs closed)
11. Eficácia por provider/modelo (taxa de aceitação)

Mais 3 alerts SQL: custo 24h excedido, taxa de falha do LLM alta, erro repetido em janela curta.

---

## Feedback loop

Quando um PR criado pelo Observer é mergeado ou fechado, uma GitHub Action atualiza automaticamente a tabela de diagnósticos:

```yaml
# .github/workflows/observer-feedback.yml
on:
  pull_request:
    types: [closed]

jobs:
  update-diagnostics:
    if: startsWith(github.event.pull_request.head.ref, 'fix/agent-auto-')
    # ... chama deploy/update_pr_feedback.py
```

Isso fecha o loop: o dashboard SQL passa a mostrar quantos PRs são mergeados vs fechados, o tempo médio de aceitação, e qual provider/modelo gera fixes mais aceitos.

---

## Testes

218 testes unitários cobrindo todos os componentes:

```
test_config.py        21 testes  — ObserverConfig + load + hierarquia
test_dedup.py         14 testes  — check_duplicate + safe defaults
test_feedback.py      12 testes  — update_pr_feedback + migrations
test_multifile.py     13 testes  — normalized_fixes + parse
test_persistence.py   19 testes  — cost calc + hash + build_record
test_triggering.py     5 testes  — failure detection
test_validator.py     25 testes  — syntax + ruff + should_run_ruff
test_workflow_observer.py  2 testes — build_context
```

Rodar: `pytest observer-framework/tests/ -v`

---

## Roadmap

O framework foi implementado em 8 tracks sequenciais, todas completas:

| # | Track | Descrição |
|---|-------|-----------|
| 1 | Trigger automático | Task sentinel com `run_if: AT_LEAST_ONE_FAILED` |
| 2 | Observabilidade | Tabela `observer.diagnostics` + dashboard SQL |
| 3 | Deduplicação | Cache via hash SHA-256 + status do PR |
| 4 | Dry-run | Diagnostica sem criar PR |
| 5 | Config como código | YAML versionado no repo |
| 6 | Validação pré-PR | `compile` + `ruff` antes do PR |
| 7 | Multi-file fixes | Lista de `fixes` no `DiagnosisResult` |
| 8 | Feedback loop | GitHub Action atualiza status do PR |

Ver [CHANGELOG.md](./CHANGELOG.md) para os detalhes de cada track.

### Melhorias futuras (não implementadas)

- **Pytest pré-PR.** Validação sintática existe; rodar testes unitários relevantes ao arquivo alterado em sandbox isolado.
- **Auto-retry após merge.** Quando um PR do Observer é mergeado, disparar re-execução do job que falhou para validar o fix em produção.
- **Scoring de confiança pós-fix.** Substituir a confiança auto-declarada do LLM por um score baseado em testes reais que passaram.
- **Providers adicionais.** GitLab, Bitbucket, Ollama (LLM local), Groq.
- **Multi-model ensemble.** Consultar múltiplos LLMs e votar no diagnóstico com maior concordância.
- **Context window compression.** Para notebooks muito grandes, resumir antes de enviar ao LLM.
- **Cost budget diário.** Cortar execução quando `estimated_cost_usd` do dia ultrapassa um limite configurável (já temos o campo `max_tokens_per_day` reservado).

---

## Contribuindo

Ver [CONTRIBUTING.md](./CONTRIBUTING.md) para setup, convenções, testes e processo de PR.

Dúvidas sobre arquitetura e padrões: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).
Como adicionar um novo provider: [docs/EXTENDING.md](./docs/EXTENDING.md).

---

## Licença

MIT. Ver [LICENSE](./LICENSE).

---

## Créditos

Framework criado em abril de 2026 como parte de um pipeline Medallion real rodando em Databricks + AWS. Validado end-to-end contra chaos tests que injetam falhas controladas (schema inválido, NULLs em dedup, divisão por zero, quality check estrito).

O objetivo original era um teste técnico de data engineering. Virou um produto.
