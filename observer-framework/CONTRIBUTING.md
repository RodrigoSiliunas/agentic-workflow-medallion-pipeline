# Contribuindo com o Observer Agent

Obrigado pelo interesse! Este documento cobre setup local, padrões de código, como rodar testes e o processo de PR.

## Setup local

Requisitos:
- Python 3.11+
- `pip` ou `uv`
- Opcional: `ruff` no PATH para que a validação pré-PR execute completamente

```bash
git clone https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline.git
cd agentic-workflow-medallion-pipeline/pipeline
python -m venv .venv
source .venv/bin/activate     # Linux/Mac
.venv\Scripts\activate         # Windows

pip install -e .[dev]
pip install pyyaml pydantic anthropic PyGithub databricks-sdk
```

## Rodando testes

```bash
# Todos os testes do Observer
pytest tests/test_observer/ -v

# Um arquivo específico
pytest tests/test_observer/test_dedup.py -v

# Com cobertura (se tiver pytest-cov instalado)
pytest tests/test_observer/ --cov=observer --cov-report=term-missing
```

Todos os testes devem passar antes de abrir PR.

## Rodando lint

```bash
ruff check observer/
ruff check observer/ --fix  # auto-fix
```

Configuração de lint está em `pipeline/pyproject.toml`. Respeitamos `line-length=100` e `target-version=py311`.

## Padrões de código

### Python

- **Type hints sempre.** Funções públicas e privadas devem ter annotations de parâmetros e retorno.
- **Dataclasses para DTOs.** `DiagnosisRequest`, `DiagnosisResult`, `PRResult`, `DuplicateCheckResult`, `ValidationResult`, `DiagnosticRecord` seguem esse padrão. Prefira `@dataclass` em vez de `TypedDict` para classes que o runtime precisa instanciar.
- **`from __future__ import annotations`** no topo de todo arquivo novo, para forward references funcionarem sem custo.
- **Helpers privados com `_` prefix.** `_run_ruff`, `_check_syntax`, `_coerce_bool`, `_parse_ruff_json`, `_migrate_columns`, `_read_config_file`.
- **Docstrings em PT-BR** quando o público alvo é desenvolvedor brasileiro (é o caso desse projeto), mas sinta-se à vontade para contribuir em inglês se preferir — vamos normalizar no futuro.
- **Nada de inline imports.** Todos os imports ficam no topo do arquivo. Exceção: lazy imports de dependências opcionais (`anthropic`, `openai`, `PyGithub`) dentro de métodos para permitir instalação parcial.
- **Sem comentários óbvios.** Só comente o porquê, nunca o que. Código bem nomeado se explica.

### Pydantic compatibility

**IMPORTANTE:** O Databricks Runtime traz Pydantic V1 pré-instalado. Código que usa features V2-only quebra em runtime.

Evite:
- `from pydantic import field_validator, ConfigDict` — V2-only
- `model_config = ConfigDict(extra="forbid")` — V2-only
- `@field_validator` — V2-only
- `Model.model_fields` — V2-only
- `instance.model_dump()` / `Model.model_validate()` — V2-only

Use:
- `class Config: extra = "forbid"` — aceito em V1 e V2 (com deprecation warning em V2, que é inofensivo)
- Helpers externos de coerção em vez de `@field_validator`
- `getattr(Model, "model_fields", None) or Model.__fields__`

### Commits

Conventional Commits em português:

```
feat: descrição curta (track referente)
fix: descrição curta
refactor: descrição curta
docs: descrição curta
test: descrição curta
```

Body do commit pode detalhar o "porquê" e listar impactos. Exemplo:

```
feat: observer dedup via cache na tabela diagnostics

- check_duplicate() consulta observer.diagnostics por error_hash
- Safe defaults: em caso de erro, marca como duplicate
- GitHubProvider.get_pr_status implementado
- 14 testes unitários

Validated: chaos test 398124681222072 -> cache HIT, cost=$0.00
```

### Branches

Branches de feature: `feat/observer-dedup`, `feat/observer-validation`.
Branches de fix: `fix/observer-pydantic-v1-compat`.
PRs do próprio Observer (automáticos): `fix/agent-auto-{task}-{timestamp}`.

Base branch default: `dev`. `main` só recebe merges de `dev` validados.

## Adicionando um novo provider

### LLM provider

1. Crie `providers/seu_provider.py`:

   ```python
   from observer.providers import register_llm_provider
   from observer.providers.base import (
       DiagnosisRequest, DiagnosisResult, LLMProvider, with_retry,
   )

   @register_llm_provider("seu_provider")
   class SeuProvider(LLMProvider):
       def __init__(self, api_key: str = "", model: str = "default-model", max_tokens: int = 16000):
           self._api_key = api_key
           self._model = model
           self._max_tokens = max_tokens

       @property
       def name(self) -> str:
           return "seu_provider"

       @with_retry(max_retries=3, base_delay=2.0)
       def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
           # 1. Constrói prompt
           # 2. Chama a API
           # 3. Parse da resposta para dict
           # 4. Retorna DiagnosisResult
           ...
   ```

2. Adicione a importação lazy em `providers/__init__.py` (ver padrão do anthropic/openai).

3. Adicione preços na constante `PRICING` em `persistence.py` para que `calculate_cost_usd` funcione.

4. Escreva testes em `tests/test_observer/test_seu_provider.py`.

### Git provider

1. Crie `providers/seu_git_provider.py`:

   ```python
   @register_git_provider("seu_git")
   class SeuGitProvider(GitProvider):
       @property
       def name(self) -> str:
           return "seu_git"

       @with_retry(max_retries=3, base_delay=2.0)
       def create_fix_pr(self, diagnosis, failed_task) -> PRResult:
           fixes = diagnosis.normalized_fixes()
           # Cria branch, commita arquivos, abre PR
           ...

       def get_pr_status(self, pr_number: int) -> str:
           # Retorna 'open', 'merged', 'closed' ou 'unknown'
           ...
   ```

2. Testes + entrada em `providers/__init__.py`.

## Processo de PR

1. Fork do repo
2. Branch a partir de `dev`
3. Implementação + testes
4. `ruff check` limpo
5. `pytest` passando
6. Commit com Conventional Commits
7. Push e abrir PR para `dev`
8. PR description deve conter:
   - Qual track/feature implementa
   - Resumo das mudanças
   - Como foi testado (testes unitários + validação real se aplicável)
   - Screenshots/logs se for visual ou comportamental

Todos os PRs passam pelo CI (`ruff` + `pytest`). Ver `.github/workflows/ci.yml`.

## Design principles

1. **Agnosticismo.** O Observer não deve conhecer nada específico do pipeline Medallion. Código que fala "bronze", "silver", "gold" não pertence aqui.
2. **Providers plugáveis.** Adicionar um provider LLM/Git novo não deve requerer mudanças no core. Factory + registry.
3. **Falhas não-críticas não bloqueiam.** Persistência, observabilidade, dedup são diferenciais — se falharem, o fluxo principal segue. Sempre `try/except` no opcional.
4. **Safe defaults no dedup.** Em caso de incerteza, prefira não criar PR a criar um duplicado.
5. **Retrocompatibilidade.** Mudanças em dataclasses (ex: adicionar `fixes` ao `DiagnosisResult`) devem manter o formato antigo funcionando via fallback.
6. **Compatível com Pydantic V1.** Databricks Runtime = V1. Veja a seção de padrões acima.

## Dúvidas

Abra uma issue no GitHub ou um draft PR com `[WIP]` no título para discutir antes de implementar.
