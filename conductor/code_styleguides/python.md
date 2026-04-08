# Python Style Guide

## Formatacao e Linting

- **Formatter/Linter**: `ruff` (substitui black + isort + flake8)
- **Line length**: 100 caracteres
- **Quotes**: Double quotes (`"`)
- **Indent**: 4 espacos

```toml
# ruff config em pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]

[tool.ruff.format]
quote-style = "double"
```

## Type Hints

- Type hints obrigatorios em funcoes publicas da `lib/`
- Type hints opcionais em notebooks (PySpark tem tipagem propria)
- Usar tipos modernos: `list[str]`, `dict[str, int]`, `str | None`

```python
# Sim
def extract_cpf(text: str) -> list[str]:
    ...

def mask_cpf(cpf: str) -> str:
    ...

# Nao
def extract_cpf(text):
    ...
```

## Docstrings

- Docstrings apenas em funcoes publicas da `lib/`
- Formato conciso, uma linha quando possivel
- Sem docstrings em funcoes internas obvias

```python
# Sim
def mask_cpf(cpf: str) -> str:
    """'418.696.561-30' -> '***.***.561-30'. Preserva ultimos 5 digitos."""

# Nao
def mask_cpf(cpf: str) -> str:
    """
    Masks a CPF number by replacing the first digits with asterisks.

    Args:
        cpf: The CPF string to mask.

    Returns:
        The masked CPF string.
    """
```

## Imports

- Ordenados por `ruff` (isort-compatible)
- Agrupamento: stdlib → third-party → local
- Sem wildcard imports (`from x import *`)

## Naming

| Tipo | Convencao | Exemplo |
|------|-----------|---------|
| Modulos | snake_case | `dedup_clean.py` |
| Funcoes | snake_case | `extract_cpf()` |
| Classes | PascalCase | `SchemaValidator` |
| Constantes | UPPER_SNAKE | `REQUIRED_COLUMNS` |
| Variaveis | snake_case | `masked_cpf` |
| Regex patterns | UPPER_SNAKE | `CPF_PATTERN` |

## Patterns Especificos do Projeto

### Extratores (lib/extractors/)

```python
# Cada extrator segue o mesmo contrato
PATTERN = r'\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b'

def extract(text: str) -> list[str]:
    """Extrai todas as ocorrencias do padrao no texto."""
    return re.findall(PATTERN, text)

def validate(value: str) -> bool:
    """Valida se o valor extraido e valido (ex: digitos verificadores)."""
    ...

def mask(value: str) -> str:
    """Mascara o valor preservando formato e dimensoes."""
    ...
```

### Notebooks Databricks

```python
# Inicio de cada notebook: ler task values do agente
should_process = dbutils.jobs.taskValues.get(
    taskKey="agent_pre", key="should_process", default=False
)
if not should_process:
    dbutils.notebook.exit("SKIP")

# Final de cada notebook: registrar metricas e status
dbutils.jobs.taskValues.set(key="status", value="SUCCESS")
```

### Testes (tests/)

```python
# Nomear testes descritivamente
def test_extract_cpf_com_pontuacao():
    assert extract("meu cpf eh 418.696.561-30") == ["418.696.561-30"]

def test_extract_cpf_sem_pontuacao():
    assert extract("cpf 41869656130") == ["41869656130"]

def test_mask_cpf_preserva_ultimos_5():
    assert mask("418.696.561-30") == "***.***.561-30"
```

## Anti-Patterns

- Nao usar `print()` em notebooks — usar `logger.info()`
- Nao usar `import *`
- Nao hardcodar paths S3 — usar variaveis/config
- Nao usar fallback/default para chaves de seguranca
- Nao criar abstrações prematuras — 3 linhas repetidas > 1 classe desnecessaria
