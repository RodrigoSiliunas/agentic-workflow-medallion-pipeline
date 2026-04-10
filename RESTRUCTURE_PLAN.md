# Plano de Reestruturação — Observer Framework + Pipelines

**Objetivo:** Separar o Observer Framework (reusável, futuro repo open-source) do pipeline específico WhatsApp, para que a pasta `pipelines/` possa abrigar múltiplos pipelines no futuro (one-click deploy de vários templates).

---

## Estrutura atual vs. proposta

### Atual

```
Teste Técnico/
├── pipeline/                              ← misturado: framework + pipeline específico
│   ├── notebooks/
│   │   ├── pre_check.py
│   │   ├── bronze/, silver/, gold/, validation/
│   │   └── observer/
│   │       ├── collect_and_fix.py         ← integra framework com este deploy
│   │       └── trigger_sentinel.py        ← idem
│   ├── pipeline_lib/
│   │   ├── agent/
│   │   │   ├── observer/                  ← FRAMEWORK
│   │   │   ├── github_pr.py               ← legacy (remover)
│   │   │   └── llm_diagnostics.py         ← legacy (remover)
│   │   ├── storage/, schema/, extractors/, masking/   ← específicos WhatsApp
│   │   └── __init__.py
│   ├── deploy/
│   │   ├── update_pr_feedback.py          ← genérico do framework
│   │   ├── dashboard_queries.sql          ← genérico do framework
│   │   └── outros scripts                 ← específicos WhatsApp
│   ├── tests/
│   │   ├── test_observer/                 ← FRAMEWORK
│   │   └── test_{deploy,extractors,masking,schema}/   ← específicos WhatsApp
│   ├── observer_config.yaml               ← config específica deste deploy
│   └── pyproject.toml
```

### Proposta

```
Teste Técnico/
├── observer-framework/                    ← repo standalone futuro
│   ├── README.md, LICENSE, .gitignore
│   ├── CHANGELOG.md, CONTRIBUTING.md
│   ├── docs/
│   │   ├── ARCHITECTURE.md
│   │   ├── USAGE.md
│   │   └── EXTENDING.md
│   ├── observer_agent/                    ← pacote Python
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── dedup.py
│   │   ├── persistence.py
│   │   ├── triggering.py
│   │   ├── validator.py
│   │   ├── workflow_observer.py
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── anthropic_provider.py
│   │       ├── openai_provider.py
│   │       └── github_provider.py
│   ├── tests/                             ← testes do framework (119 testes)
│   │   ├── test_config.py
│   │   ├── test_dedup.py
│   │   ├── test_feedback.py
│   │   ├── test_multifile.py
│   │   ├── test_persistence.py
│   │   ├── test_triggering.py
│   │   ├── test_validator.py
│   │   └── test_workflow_observer.py
│   ├── scripts/
│   │   └── update_pr_feedback.py          ← CLI genérico para GitHub Action
│   ├── templates/
│   │   ├── observer_config.yaml           ← template com defaults documentados
│   │   ├── dashboard_queries.sql          ← queries SQL genéricas
│   │   └── notebooks/
│   │       ├── collect_and_fix.py         ← notebook exemplo de integração
│   │       └── trigger_sentinel.py        ← sentinel exemplo
│   └── pyproject.toml                     ← pacote independente
│
├── pipelines/                             ← guarda-chuva para múltiplos pipelines
│   └── pipeline-seguradora-whatsapp/      ← pipeline atual
│       ├── notebooks/
│       │   ├── pre_check.py
│       │   ├── bronze/, silver/, gold/, validation/
│       │   └── observer/                  ← copias dos templates do framework
│       │       ├── collect_and_fix.py     (adaptado se necessário)
│       │       └── trigger_sentinel.py
│       ├── pipeline_lib/                  ← só código específico WhatsApp
│       │   ├── __init__.py
│       │   ├── storage/s3_client.py
│       │   ├── schema/
│       │   ├── extractors/   (CPF, phone, email, etc — pt-BR específicos)
│       │   └── masking/      (HMAC para PII de seguros)
│       ├── deploy/                        ← scripts específicos WhatsApp
│       │   ├── create_workflow.py
│       │   ├── create_observer_workflow.py
│       │   ├── setup_catalog.py
│       │   ├── upload_data.py
│       │   ├── trigger_run.py
│       │   └── trigger_chaos.py
│       ├── tests/                         ← testes específicos WhatsApp
│       │   ├── test_deploy/
│       │   ├── test_extractors/
│       │   ├── test_masking/
│       │   └── test_schema/
│       ├── data/                          ← dados de sample (gitignored)
│       ├── observer_config.yaml           ← config deste deploy
│       └── pyproject.toml                 ← depende do observer-framework local
│
├── platform/                              ← inalterado (frontend + backend da plataforma)
├── infra/                                 ← inalterado (Terraform AWS)
├── conductor/                             ← inalterado (metadados do monorepo)
├── docs/                                  ← inalterado (análise arquitetural)
├── .github/workflows/
│   ├── ci.yml                             ← atualizado para testar ambos
│   ├── cd.yml                             ← atualizado com path novo do Databricks Repo
│   └── observer-feedback.yml              ← atualizado com caminho do update_pr_feedback.py
├── CLAUDE.md                              ← atualizado
├── AGENTS.md                              ← atualizado
├── CODEX_MANUAL.md                        ← atualizado
├── CODEX_TRACKS_PROMPT.md                 ← atualizado
├── RESTRUCTURE_PLAN.md                    ← este documento (deletar apos concluir)
└── README.md                              ← atualizado
```

---

## Decisões de design

### 1. Nome do pacote Python: `observer_agent`

**Por quê:** descritivo, único, sem conflito com nomes builtin (`observer` colide com padrões conceituais), consistente com o padrão `{nome}_agent` usado em frameworks de IA.

**Import resultante:**
```python
# Antes
from pipeline_lib.agent.observer import ObserverDiagnosticsStore

# Depois
from observer_agent import ObserverDiagnosticsStore
```

### 2. Notebooks de integração ficam **no pipeline**, não no framework

`collect_and_fix.py` e `trigger_sentinel.py` são notebooks Databricks, não código Python puro. Eles precisam:
- Ler `dbutils.secrets` específicos do workspace
- Conhecer paths do Repo Databricks do pipeline
- Rodar em cluster específico

**Decisão:** ficam em `pipelines/pipeline-seguradora-whatsapp/notebooks/observer/` como código do deploy. O framework oferece **templates** em `observer-framework/templates/notebooks/` que cada novo pipeline pode copiar e ajustar.

### 3. `update_pr_feedback.py` vai para `observer-framework/scripts/`

É um CLI 100% genérico — só precisa de `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `--pr-number`, `--status`, `--catalog`. Zero lógica específica de pipeline.

### 4. `dashboard_queries.sql` vai para `observer-framework/templates/`

Todas as queries operam na tabela `{catalog}.observer.diagnostics`, que é do framework. Pipelines podem criar queries adicionais específicas se precisarem.

### 5. `observer_config.yaml` fica no pipeline, template no framework

Cada deploy tem seu próprio config (provider, modelo, dedup window). O framework oferece um **template documentado** em `observer-framework/templates/observer_config.yaml`.

### 6. Dependência pipeline → framework via pip install local editável

No `pyproject.toml` do pipeline:

```toml
[project]
dependencies = [
    "observer-agent @ file:../../observer-framework",
    "pydantic>=2.0",
    "pyyaml>=6.0",
]
```

Isso permite desenvolvimento editável (mudanças no framework refletem no pipeline imediatamente) e deploy independente no futuro (publicar observer-agent no PyPI e instalar via versão).

No Databricks, o pipeline vai precisar instalar o framework via `%pip install`. Opções:
- **A)** Commit o framework no Databricks Repo e adicionar ao `sys.path` (como fazemos hoje)
- **B)** Publicar wheel do framework no PyPI e `%pip install observer-agent`
- **C)** Usar `%pip install git+https://github.com/...` durante transição

**Decisão:** começar com (A) via `sys.path` apontando para `observer-framework/observer_agent`. Migrar para (B) quando publicar.

### 7. Conductor e docs/ ficam na raiz

São metadados do monorepo inteiro, não de um componente específico. Tracks futuras podem ser sobre framework OU pipeline OU plataforma.

### 8. Arquivos legacy a deletar

Durante o refactor, deletar:
- `pipeline/pipeline_lib/agent/github_pr.py` (substituído pelo `GitHubProvider`)
- `pipeline/pipeline_lib/agent/llm_diagnostics.py` (substituído pelos providers LLM)

Esses arquivos são restos de iterações anteriores e não são importados por ninguém.

---

## Plano em 6 fases

### Fase 1 — Scaffolding das pastas novas (sem mover nada)

- Criar `observer-framework/` e `pipelines/pipeline-seguradora-whatsapp/` vazias
- Criar subpastas: `observer-framework/{observer_agent,tests,scripts,templates,templates/notebooks,docs}`
- Criar subpastas: `pipelines/pipeline-seguradora-whatsapp/{notebooks,pipeline_lib,deploy,tests,data}`
- Criar `pyproject.toml` novo em `observer-framework/` (pacote standalone)
- Criar `pyproject.toml` novo em `pipelines/pipeline-seguradora-whatsapp/` (depende do framework)

**Critério de sucesso:** `ls` mostra as pastas vazias, sem quebrar nada existente.

### Fase 2 — Mover framework do Observer

Arquivos que vão para `observer-framework/observer_agent/`:
- `pipeline/pipeline_lib/agent/observer/config.py`
- `pipeline/pipeline_lib/agent/observer/dedup.py`
- `pipeline/pipeline_lib/agent/observer/persistence.py`
- `pipeline/pipeline_lib/agent/observer/triggering.py`
- `pipeline/pipeline_lib/agent/observer/validator.py`
- `pipeline/pipeline_lib/agent/observer/workflow_observer.py`
- `pipeline/pipeline_lib/agent/observer/__init__.py`
- `pipeline/pipeline_lib/agent/observer/providers/` (diretório inteiro)

Documentação que vai para `observer-framework/`:
- `pipeline/pipeline_lib/agent/observer/README.md`
- `pipeline/pipeline_lib/agent/observer/LICENSE`
- `pipeline/pipeline_lib/agent/observer/.gitignore`
- `pipeline/pipeline_lib/agent/observer/CHANGELOG.md`
- `pipeline/pipeline_lib/agent/observer/CONTRIBUTING.md`
- `pipeline/pipeline_lib/agent/observer/docs/` (diretório inteiro)

Testes que vão para `observer-framework/tests/`:
- `pipeline/tests/test_observer/*.py` (8 arquivos de teste)

Scripts que vão para `observer-framework/scripts/`:
- `pipeline/deploy/update_pr_feedback.py`

Templates que vão para `observer-framework/templates/`:
- `pipeline/deploy/dashboard_queries.sql` → `observer-framework/templates/dashboard_queries.sql`
- Cópia de `pipeline/notebooks/observer/collect_and_fix.py` → `observer-framework/templates/notebooks/collect_and_fix.py`
- Cópia de `pipeline/notebooks/observer/trigger_sentinel.py` → `observer-framework/templates/notebooks/trigger_sentinel.py`
- Cópia de `pipeline/observer_config.yaml` → `observer-framework/templates/observer_config.yaml` (sem valores específicos)

**Atualizações de código durante a mudança:**
- Imports dentro de `observer_agent/`: `from pipeline_lib.agent.observer.X` → `from observer_agent.X`
- Imports dentro dos testes: idem

Deletar após mover:
- `pipeline/pipeline_lib/agent/observer/` (vazio)
- `pipeline/pipeline_lib/agent/github_pr.py` (legacy)
- `pipeline/pipeline_lib/agent/llm_diagnostics.py` (legacy)
- `pipeline/pipeline_lib/agent/` (vazio)
- `pipeline/tests/test_observer/` (vazio)

**Critério de sucesso:** `cd observer-framework && pytest tests/` passa 119 testes. `ruff check observer_agent/` limpo.

### Fase 3 — Mover pipeline WhatsApp

Código para `pipelines/pipeline-seguradora-whatsapp/pipeline_lib/`:
- `pipeline/pipeline_lib/storage/` (diretório inteiro)
- `pipeline/pipeline_lib/schema/` (diretório inteiro)
- `pipeline/pipeline_lib/extractors/` (diretório inteiro)
- `pipeline/pipeline_lib/masking/` (diretório inteiro)
- `pipeline/pipeline_lib/__init__.py`

Notebooks para `pipelines/pipeline-seguradora-whatsapp/notebooks/`:
- `pipeline/notebooks/pre_check.py`
- `pipeline/notebooks/bronze/` (diretório)
- `pipeline/notebooks/silver/` (diretório)
- `pipeline/notebooks/gold/` (diretório)
- `pipeline/notebooks/validation/` (diretório)
- `pipeline/notebooks/observer/collect_and_fix.py` (mantém aqui, é deploy-specific)
- `pipeline/notebooks/observer/trigger_sentinel.py` (idem)

Deploy scripts para `pipelines/pipeline-seguradora-whatsapp/deploy/`:
- `pipeline/deploy/create_workflow.py`
- `pipeline/deploy/create_observer_workflow.py`
- `pipeline/deploy/setup_catalog.py`
- `pipeline/deploy/trigger_chaos.py`
- `pipeline/deploy/trigger_run.py`
- `pipeline/deploy/upload_data.py`

Testes para `pipelines/pipeline-seguradora-whatsapp/tests/`:
- `pipeline/tests/test_deploy/`
- `pipeline/tests/test_extractors/`
- `pipeline/tests/test_masking/`
- `pipeline/tests/test_schema/`
- `pipeline/tests/fixtures/`
- `pipeline/tests/__init__.py`

Outros:
- `pipeline/observer_config.yaml` → `pipelines/pipeline-seguradora-whatsapp/observer_config.yaml`
- `pipeline/data/` → `pipelines/pipeline-seguradora-whatsapp/data/`

Deletar após mover:
- `pipeline/` (vazio, exceto caches pytest que também serão removidos)

**Critério de sucesso:** estrutura de `pipelines/pipeline-seguradora-whatsapp/` espelha a proposta. Diretório `pipeline/` inexistente ou vazio.

### Fase 4 — Atualizar imports no pipeline WhatsApp

Todos os notebooks e testes que usam `from pipeline_lib.agent.observer import X` viram `from observer_agent import X`.

Arquivos afetados:
- `notebooks/observer/collect_and_fix.py`
- `notebooks/observer/trigger_sentinel.py`
- Testes `test_deploy/` se importam do observer

Setup do pipeline para enxergar o observer-framework no cluster Databricks:

Opção escolhida na decisão 6 — adicionar ao `sys.path` nos notebooks:
```python
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:4])
OBSERVER_FRAMEWORK = f"/Workspace{_repo_root}/observer-framework"
PIPELINE_LIB = f"/Workspace{_repo_root}/pipelines/pipeline-seguradora-whatsapp"
sys.path.insert(0, OBSERVER_FRAMEWORK)   # para importar observer_agent
sys.path.insert(0, PIPELINE_LIB)         # para importar pipeline_lib
```

No dev local, o `pyproject.toml` do pipeline usa `file://` para o observer-framework:
```toml
dependencies = [
    "observer-agent @ file://../../observer-framework",
    ...
]
```

**Critério de sucesso:** `pytest pipelines/pipeline-seguradora-whatsapp/tests/` passa. Notebooks (validação via `ast.parse`) compilam.

### Fase 5 — Atualizar CI/CD e Databricks deploy

**`.github/workflows/ci.yml`** (atualizar paths):
- Rodar `ruff check observer-framework/observer_agent/`
- Rodar `pytest observer-framework/tests/`
- Rodar `ruff check pipelines/pipeline-seguradora-whatsapp/pipeline_lib/`
- Rodar `pytest pipelines/pipeline-seguradora-whatsapp/tests/`

**`.github/workflows/cd.yml`** (atualizar repo path):
- Manter sincronização do Databricks Repo
- O `DATABRICKS_REPO_PATH` continua o mesmo (`/Repos/administrator@idlehub.com.br/agentic-workflow-medallion-pipeline`)
- O conteúdo dentro do repo no Databricks vai ter a estrutura nova

**`.github/workflows/observer-feedback.yml`** (atualizar caminho do script):
- Antes: `python pipeline/deploy/update_pr_feedback.py`
- Depois: `python observer-framework/scripts/update_pr_feedback.py`

**`pipelines/pipeline-seguradora-whatsapp/deploy/create_workflow.py`** (atualizar notebook paths):
- `nb("pre_check")` agora aponta para `/Repos/.../pipelines/pipeline-seguradora-whatsapp/notebooks/pre_check`
- Todos os outros notebook paths seguem o mesmo reajuste

**`create_observer_workflow.py`**: mesmo ajuste de path para o notebook `observer/collect_and_fix`

**Critério de sucesso:** CI passa no push. Workflow Databricks pode ser deployado sem erros (o deploy real vai ser um teste separado depois do refactor).

### Fase 6 — Atualizar documentação do monorepo

- `CLAUDE.md`: nova estrutura do monorepo, caminhos atualizados
- `AGENTS.md`: idem (versão resumida)
- `CODEX_MANUAL.md`: manual atualizado para Codex com nova estrutura
- `CODEX_TRACKS_PROMPT.md`: ajustar paths nos exemplos
- `conductor/tech-stack.md`: refletir a nova separação
- `README.md` da raiz (se existir): atualizar

Depois: deletar `RESTRUCTURE_PLAN.md` (este arquivo).

**Critério de sucesso:** documentação coerente com a estrutura real.

---

## Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Imports quebrados no Databricks cluster | Testar via notebook rápido antes de fazer deploy do workflow. O `sys.path.insert` precisa apontar para o path correto dentro de `/Workspace/Repos/...` |
| Testes escondidos que importam de paths antigos | Rodar `grep -r "pipeline_lib.agent.observer"` antes e depois para garantir 0 referências legacy |
| CI quebrar por arquivo não-movido | Fase 1 cria estrutura sem apagar nada. As Fases 2-3 fazem moves atômicos. Commits por fase permitem rollback granular |
| `observer_config.yaml` path mudou mas `load_observer_config` não sabe | O `collect_and_fix.py` já calcula `CONFIG_PATH = f"{PIPELINE_ROOT}/observer_config.yaml"`. Atualizar essa linha para apontar para o pipeline path. |
| Dashboard queries referenciando tabela específica | `medallion.observer.diagnostics` é genérico, não muda. Queries continuam válidas. |
| Feedback loop da GitHub Action quebrar | Ajustar path do script no workflow YAML (Fase 5) |
| Databricks Repo dessincronizado durante transição | Fazer o refactor em branch separada (`refactor/monorepo-structure`), validar localmente, dar merge num único commit grande para o main |

---

## Estratégia de execução

### Branch e commits

Criar branch `refactor/observer-framework-split` a partir de `main`. Commits por fase:

1. `refactor: fase 1 - scaffold das pastas observer-framework e pipelines`
2. `refactor: fase 2 - move observer framework para observer-framework/`
3. `refactor: fase 3 - move pipeline WhatsApp para pipelines/pipeline-seguradora-whatsapp/`
4. `refactor: fase 4 - atualiza imports para observer_agent`
5. `refactor: fase 5 - atualiza CI/CD e paths do Databricks`
6. `docs: fase 6 - atualiza CLAUDE/AGENTS/CODEX com nova estrutura`

Cada commit deve ter todos os testes passando e lint limpo. Se algo quebrar, é possível `git revert` só daquela fase.

Depois de todas as fases:
- Push da branch
- Abrir PR para `main`
- Validar CI
- Merge via squash (opcional, para manter main limpo)

### Validação em cada fase

**Após Fase 2:**
```bash
cd observer-framework
pytest tests/                       # 119 testes
ruff check observer_agent/          # lint limpo
```

**Após Fase 3:**
```bash
cd pipelines/pipeline-seguradora-whatsapp
pytest tests/                       # ~60 testes (sem os 119 do framework)
ruff check pipeline_lib/ deploy/   # lint limpo
```

**Após Fase 4:**
```bash
# Todos os testes
cd observer-framework && pytest && cd ../..
cd pipelines/pipeline-seguradora-whatsapp && pytest && cd ../..
# grep não deve encontrar referências legacy
grep -r "pipeline_lib.agent.observer" . --include="*.py"  # deve retornar vazio
```

**Após Fase 5:**
```bash
# Simular o que o CI faz
ruff check observer-framework/observer_agent/ pipelines/pipeline-seguradora-whatsapp/
pytest observer-framework/tests/ pipelines/pipeline-seguradora-whatsapp/tests/
```

**Após Fase 6:**
- Revisar manualmente `CLAUDE.md`, `AGENTS.md`, `CODEX_MANUAL.md` para garantir que refletem a estrutura nova
- Confirmar que não há referências a `pipeline/pipeline_lib/agent/observer`

### Validação no Databricks (pós-merge)

Depois do merge em `main`, o CD sincroniza o Repo. Validar:

1. `conductor/status` via Claude ou verificar que o workflow ETL e o Observer job ainda disparam corretamente
2. Rodar um chaos test em `dry_run=true` para garantir que o fluxo end-to-end ainda funciona com a nova estrutura

---

## Perguntas para confirmação

Antes de começar a implementar, quero confirmar algumas decisões:

1. **Nome do pacote:** `observer_agent` está ok? Alternativas seriam `observer_framework` ou `observer`. (Minha recomendação: `observer_agent`.)

2. **Notebooks de integração:** manter em `pipelines/pipeline-seguradora-whatsapp/notebooks/observer/` (como proposto) ou você prefere no framework como templates obrigatórios?

3. **Arquivos legacy** (`github_pr.py` e `llm_diagnostics.py` em `pipeline/pipeline_lib/agent/`): confirma que posso deletar? Eles foram substituídos pelos providers e não são importados por ninguém atualmente.

4. **Dependência pipeline → framework:** seguir com `pip install -e file://../../observer-framework` para dev local e `sys.path.insert` no Databricks, conforme decisão 6?

5. **Branch:** criar branch `refactor/observer-framework-split` e depois fazer PR para `main`? Ou prefere commitar direto em `main`?

Assim que você aprovar (com os ajustes que achar necessários), eu começo pela Fase 1.
