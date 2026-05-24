# Checklist — Pipeline Editor (pós-deploy VPS)

Base URL: **https://flowertex.idlehub.com.br**  
SSH: `ssh hostinger-vps`  
Diretório deploy: `/opt/flowertex`

---

## Estado atual do VPS (baseline — verificado em 2026-05-23)

| Item | Resultado |
|------|-----------|
| Containers | ✅ backend, frontend, postgres, redis, omni healthy |
| `/health` | ✅ HTTP 200 |
| `IMAGE_TAG` | `7ffdb1fe1ad1cd2ad2239317e692d20e60284d30` (~5 dias) |
| `pipeline_editor.py` no container | ❌ **ausente** |
| OpenAPI `edit-sessions` | ❌ **ausente** |
| Alembic current | `c0b1d2e3f4a5` — falta `d4e5f6a7b8c9` |

**Conclusão:** Pipeline Editor **ainda não está no ar**. Precisa merge + release + deploy com código novo.

---

## A. Pré-deploy (local / CI)

- [ ] Código Pipeline Editor mergeado em `main`
- [ ] Migration `d4e5f6a7b8c9` com `down_revision = c0b1d2e3f4a5` (head único)
- [ ] CI verde (`pytest` + `ruff` backend)
- [ ] `release-flowertex.yml` concluiu com sucesso
- [ ] `deploy-flowertex.yml` concluiu com sucesso

---

## B. Smoke automatizado (VPS)

```bash
# Da sua máquina (PowerShell / bash):
ssh hostinger-vps 'bash -s' < deploy/hostinger/smoke-pipeline-editor.sh
```

Com API autenticada (opcional):

```bash
# Linux/macOS — exporte token JWT e UUID do pipeline
export SMOKE_API_TOKEN="seu-jwt"
export SMOKE_PIPELINE_ID="uuid-do-pipeline"
ssh hostinger-vps "SMOKE_API_TOKEN=$SMOKE_API_TOKEN SMOKE_PIPELINE_ID=$SMOKE_PIPELINE_ID bash -s" < deploy/hostinger/smoke-pipeline-editor.sh
```

**Esperado após deploy correto:** `PASS` alto, `FAIL=0`.

Checks do script:

1. Docker healthy (backend + frontend)
2. `/health` → 200
3. `pipeline_editor.py` existe no container
4. Alembic em `d4e5f6a7b8c9` + 5 tabelas `pipeline_edit*`
5. OpenAPI com `edit-sessions` e `shared/pipeline-edit`
6. Rotas Nuxt `/pipelines/*` e `/shared/pipeline-edit/*`
7. (Opcional) workspace + criar sessão via API

---

## C. Infra manual (SSH)

```bash
ssh hostinger-vps

cd /opt/flowertex
docker compose ps
grep IMAGE_TAG .env

# Migration
docker exec -w /app/platform/backend flowertex-backend uv run alembic current
docker exec flowertex-postgres psql -U flowertex -d flowertex -c \
  "SELECT tablename FROM pg_tables WHERE tablename LIKE 'pipeline_edit%' ORDER BY 1;"

# Rotas backend
docker exec flowertex-backend ls /app/platform/backend/app/api/routes/ | grep pipeline
curl -sf https://flowertex.idlehub.com.br/api/v1/openapi.json | grep edit-sessions
```

| Check | OK | Falha |
|-------|-----|-------|
| `alembic current` contém `d4e5f6a7b8c9` | migration ok | redeploy backend |
| 5 tabelas `pipeline_edit_*` | DB ok | ver logs entrypoint |
| `pipeline_editor.py` existe | código ok | imagem antiga |

---

## D. UI — telas (browser, login editor/admin)

1. **Login** → https://flowertex.idlehub.com.br/login
2. **Deploy** → criar pipeline WhatsApp ou abrir deployment existente
3. **Abrir pipeline** → botão no `DeployProgress` ou `/pipelines/{pipelineId}`

| Aba | Verificar |
|-----|-----------|
| Overview | Job Databricks, ≥1 nó Silver editável, sessões |
| Editar | Chat NL, builder Silver, botões preview/export/approve |
| Dados | Grid preview (após testar) |
| Diagrama | Mermaid Silver |
| Histórico | Sessões listadas |

Share público (sem login): `/shared/pipeline-edit/{token}` após gerar share na sessão.

---

## E. Fluxo funcional (requer credenciais tenant)

Pré-requisitos em **Settings** da empresa:

- [ ] `databricks_host` + `databricks_token` (SQL warehouse acessível)
- [ ] Tabelas Silver existentes no catalog (`medallion.silver.*`)
- [ ] `github_token` (para PR)
- [ ] LLM API key (ou `PIPELINE_EDITOR_LLM_ENABLED=false` → modo determinístico)

| Passo | Ação | Esperado |
|-------|------|----------|
| 1 | Builder: renomear/remover coluna Silver | Draft salvo |
| 2 | **Testar preview** | `status: ready`, rows before/after |
| 3 | Export CSV | Download inicia |
| 4 | Extrair prompt.md | Markdown visível |
| 5 | Share | Link `/shared/...` abre read-only |
| 6 | Aprovar **sem** preview | ❌ 400 "Preview obrigatorio" |
| 7 | Aprovar **com** preview | Diff + PR GitHub (se `create_pr: true`) |

---

## F. Permissões

| Role | Workspace | Preview | Approve PR |
|------|-----------|---------|------------|
| viewer | ✅ | ✅ | ❌ |
| editor/admin | ✅ | ✅ | ✅ |

---

## G. Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| 404 em `/pipelines/{id}` | Pipeline de outro tenant | Verificar `company_id` |
| Builder vazio (0 nós) | Template ≠ WhatsApp sem `config.manifest` | Usar template WhatsApp ou popular manifest |
| Preview `failed` | Databricks/warehouse/tabela | Settings + logs backend |
| Approve 400 | Preview não `ready` | Rodar preview antes |
| Migration não sobe | Dois heads Alembic | `down_revision` d4e5 → c0b1 |
| Código ausente no VPS | Deploy antigo | Re-run deploy-flowertex |

Logs:

```bash
ssh hostinger-vps 'docker logs flowertex-backend --tail 100'
ssh hostinger-vps 'docker logs flowertex-frontend --tail 50'
```

---

## H. Ordem recomendada

```
merge main → release → deploy → smoke script (B) → UI (D) → fluxo E (credenciais)
```
