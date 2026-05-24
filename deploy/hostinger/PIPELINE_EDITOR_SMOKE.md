# Checklist — Pipeline Editor (pós-deploy VPS)

Base URL: **https://flowertex.idlehub.com.br**  
SSH: `ssh hostinger-vps`  
Diretório deploy: `/opt/flowertex`

---

## Estado atual do VPS (pós-deploy 2026-05-23)

| Item | Resultado |
|------|-----------|
| Containers | ✅ healthy |
| `IMAGE_TAG` | `29e5c871ee6db759d4ebae649e5b44ccb16c7208` |
| Pipeline Editor | ✅ código + migration `d4e5f6a7b8c9` |

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

```powershell
# PowerShell — substitua o JWT (ver secao abaixo)
$env:SMOKE_API_TOKEN = "eyJ..."
$env:SMOKE_PIPELINE_ID = "26d264ef-2877-49ef-b914-3f6ee4d71372"
scp deploy/hostinger/smoke-pipeline-editor.sh hostinger-vps:/tmp/smoke-pipeline-editor.sh
ssh hostinger-vps "SMOKE_API_TOKEN=$env:SMOKE_API_TOKEN SMOKE_PIPELINE_ID=$env:SMOKE_PIPELINE_ID bash /tmp/smoke-pipeline-editor.sh"
```

### Como obter o JWT

O token **nao** fica em Local Storage / Session Storage (seguranca T2). Fica **so na memoria** (Pinia) enquanto a aba esta aberta.

**Metodo 1 — Network (recomendado)**

1. Login em https://flowertex.idlehub.com.br
2. F12 → **Network** (Rede) → filtro **Fetch/XHR**
3. Abra `/pipelines/26d264ef-2877-49ef-b914-3f6ee4d71372`
4. Clique num request `/api/v1/...`
5. **Headers** → **Authorization** → copie so a parte `eyJ...` (depois de `Bearer `)

**Metodo 2 — curl login**

```bash
curl -s -X POST https://flowertex.idlehub.com.br/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"SEU_EMAIL","password":"SUA_SENHA"}'
```

Campo `access_token` na resposta. Expira em ~15 min.

**Metodo 3 — Vue DevTools**

Store Pinia `auth` → campo `accessToken`.

---

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
