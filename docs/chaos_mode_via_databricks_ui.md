# Chaos Mode via Databricks UI

Guia passo-a-passo pra disparar o pipeline `medallion_pipeline_whatsapp` em **chaos mode** direto pela UI do Databricks (sem usar `trigger_chaos.py`). Testa o Observer Agent end-to-end: falha controlada → trigger sentinel → Observer dispara → Claude Opus diagnostica → PR no GitHub.

---

## Pré-requisitos

- Pipeline ETL `medallion_pipeline_whatsapp` deployed no workspace (via UI Flowertex ou `pipelines/pipeline-seguradora-whatsapp/deploy/create_workflow.py`)
- Observer Agent deployed (job `workflow_observer_agent`)
- Secrets `medallion-pipeline` populados no Databricks (`anthropic-api-key`, `github-token`, AWS keys, `masking-secret`)
- GitHub repo configurado com PAT que tem `repo` scope

---

## Modos de chaos disponíveis

| Modo | Camada | Falha injetada |
|------|--------|----------------|
| `off` | — | Pipeline normal (default) |
| `bronze_schema` | Bronze | Schema parquet inválido (drop coluna obrigatória) |
| `silver_null` | Silver | NULLs propagados pra coluna NOT NULL no dedup |
| `gold_divide_zero` | Gold | Divisão por zero no funnel |
| `validation_strict` | Validation | Threshold de qualidade impossível (errors.append forçado) |

---

## Passo 1 — Acessar workflow no Databricks

1. Login no workspace Databricks (URL via `DATABRICKS_HOST`)
2. Sidebar esquerda → **Workflows**
3. Aba **Jobs** → clicar em `medallion_pipeline_whatsapp`

## Passo 2 — Disparar com chaos_mode

### Opção A — UI "Run now with different parameters"

1. No detalhe do job, canto superior direito → menu `▼` ao lado do botão **Run now**
2. Selecionar **Run now with different parameters**
3. Modal abre com lista de widgets — localizar `chaos_mode`
4. Trocar valor de `off` para um dos modos válidos (ex: `bronze_schema`)
5. Outros widgets podem ficar default:
   - `catalog`: `medallion`
   - `scope`: `medallion-pipeline`
   - `bronze_prefix`: `bronze/`
6. Clicar **Run**

### Opção B — Aba "Tasks" → Edit task individual (mais granular)

Útil pra testar uma task isolada sem rodar o pipeline inteiro:

1. Aba **Tasks** do job
2. Clicar na task alvo (ex: `bronze_ingestion` pra testar `bronze_schema`)
3. **Run task** com override de `chaos_mode` no modal

---

## Passo 3 — Acompanhar execução

1. Aba **Runs** do job (volta automaticamente após disparar)
2. Clicar no run mais recente (status `Pending` → `Running`)
3. Visualização DAG:
   - Tasks verde = sucesso
   - Task vermelha = falha (esperado em chaos mode)
   - Task `observer_trigger` (sentinel) → vai disparar quando alguma upstream falhar (`run_if=AT_LEAST_ONE_FAILED`)

### Logs de cada task

- Clicar na task → aba **Output** mostra stdout/stderr
- Aba **Spark UI** mostra plano de execução
- Aba **Logs** = log4j completo do driver

---

## Passo 4 — Verificar trigger do Observer

Após o pipeline falhar e `observer_trigger` rodar:

1. Sidebar **Workflows** → job `workflow_observer_agent`
2. Aba **Runs** — deve aparecer um run novo com `source_run_id` apontando pro run do ETL que falhou
3. Verificar parâmetros do run (clicar no run → **Parameters**):
   ```json
   {
     "source_job_id": "<id do medallion_pipeline_whatsapp>",
     "source_run_id": "<run_id que falhou>",
     "llm_provider": "anthropic",
     "git_provider": "github",
     "observer_config_path": "/Workspace/.../observer_config.yaml"
   }
   ```

## Passo 5 — Verificar PR no GitHub

Após Observer terminar (3-8 min dependendo da complexidade):

1. Logs do Observer mostram:
   - `Coletando contexto` (Workspace API + UC schema)
   - `Diagnosticando via Claude Opus` (streaming response)
   - `Validando fix pre-PR` (compile + ast + ruff)
   - `Criando branch fix/agent-auto-<hash>` no GitHub
   - `PR criado: <url>`
2. No GitHub: `RodrigoSiliunas/agentic-workflow-medallion-pipeline/pulls`
   - PR alvo: branch `dev`
   - Título: `[Observer] Fix: <descrição da causa raiz>`
   - Body: diagnóstico + arquivos modificados + nivel de confiança

## Passo 6 — Validar tabela de diagnósticos

```sql
-- No SQL Editor do Databricks
SELECT
  diagnosed_at,
  source_run_id,
  llm_provider,
  llm_model,
  error_signature,
  confidence_score,
  pr_url,
  pr_status,
  resolution_time_ms
FROM medallion.observer.diagnostics
ORDER BY diagnosed_at DESC
LIMIT 10;
```

---

## Resetar pra modo normal

Após validar o ciclo:

1. Workflows → `medallion_pipeline_whatsapp` → **Run now with different parameters**
2. Setar `chaos_mode=off`
3. Run pra confirmar pipeline volta a passar

OU mergear o PR do Observer no GitHub → CD sincroniza com Databricks Repo → próximo run usa código corrigido.

---

## Troubleshooting

| Sintoma | Causa | Fix |
|---------|-------|-----|
| `observer_trigger` não dispara | Pipeline passou (chaos não injetou falha real) | Verificar logs da task alvo — chaos pode ter sido suprimido por widget mal-passado |
| Observer roda mas sem PR | GitHub PAT sem `repo` scope OU rate limit | `gh auth status` + checar `medallion-pipeline/github-token` |
| `Claude Opus access denied` | Anthropic key sem acesso a `claude-opus-4-7` | Trocar key OU mudar `llm_model` no `observer_config.yaml` |
| Diagnóstico genérico | Contexto insuficiente (notebook code não foi coletado) | Verificar logs `collect_notebook_code` — Workspace API token pode estar inválido |
| PR duplicado | Dedup via hash falhou | Checar tabela `observer.diagnostics` — `error_signature` deve match runs anteriores |

---

## Referências

- `pipelines/pipeline-seguradora-whatsapp/deploy/trigger_chaos.py` — script equivalente CLI
- `pipelines/pipeline-seguradora-whatsapp/notebooks/pre_check.py` — propaga `chaos_mode` via task values
- `pipelines/pipeline-seguradora-whatsapp/notebooks/{bronze,silver,gold,validation}/*.py` — blocos `if chaos_mode == "..."` que injetam falha
- `observer-framework/notebooks/collect_and_fix.py` — Observer principal
- `observer-framework/notebooks/trigger_sentinel.py` — task sentinel (run_if=AT_LEAST_ONE_FAILED)
