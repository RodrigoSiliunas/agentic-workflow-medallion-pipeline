# Extending — Adicionando providers

O Observer usa factory + registry para LLM e Git providers. Adicionar um provider novo requer:

1. Uma classe Python que implementa a interface apropriada
2. Decorator de registro
3. Lazy import no `providers/__init__.py`
4. Testes unitários
5. (LLM apenas) Preços na tabela `PRICING`

---

## Adicionando um LLM provider

Exemplo: provider para [Groq](https://groq.com) (compatível com OpenAI API).

### 1. Criar o módulo

`observer-framework/observer/providers/groq_provider.py`:

```python
"""Provider LLM: Groq (OpenAI-compatible API)."""

from __future__ import annotations

import json
import re

from observer.providers import register_llm_provider
from observer.providers.anthropic_provider import SYSTEM_PROMPT
from observer.providers.base import (
    DiagnosisRequest,
    DiagnosisResult,
    LLMProvider,
    with_retry,
)


@register_llm_provider("groq")
class GroqProvider(LLMProvider):
    """Groq API — compatível com OpenAI SDK via base_url."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "llama-3.3-70b-versatile",
        max_tokens: int = 16000,
    ):
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return "groq"

    @with_retry(max_retries=3, base_delay=2.0)
    def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "openai SDK não instalado. Instale com: pip install openai"
            ) from e

        client = OpenAI(
            api_key=self._api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        user_prompt = self._build_prompt(request)

        response = client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content or ""
        usage = response.usage
        in_tok = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0

        data = self._parse_json(text)

        return DiagnosisResult(
            diagnosis=data.get("diagnosis", ""),
            root_cause=data.get("root_cause", ""),
            fix_description=data.get("fix_description", ""),
            fixed_code=data.get("fixed_code"),
            file_to_fix=data.get("file_to_fix"),
            fixes=data.get("fixes"),
            confidence=float(data.get("confidence", 0.0)),
            requires_human_review=data.get("requires_human_review", True),
            additional_notes=data.get("additional_notes", ""),
            provider=self.name,
            model=self._model,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )

    def _build_prompt(self, req: DiagnosisRequest) -> str:
        # Mesmo formato dos outros providers
        return f"""O pipeline falhou. Diagnóstico e correção necessários.

Task: {req.failed_task}
Erro: {req.error_message}

Código:
```python
{req.notebook_code}
```

Schema: {req.schema_info}
Estado: {json.dumps(req.pipeline_state, indent=2, default=str)}

Responda em JSON com: diagnosis, root_cause, fix_description,
fixed_code, file_to_fix, confidence, requires_human_review,
additional_notes.

Para fix em múltiplos arquivos use `fixes` como lista
[{{"file_path": "...", "code": "..."}}]."""

    def _parse_json(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return {
                "diagnosis": text[:500],
                "confidence": 0.3,
                "requires_human_review": True,
            }
```

### 2. Registrar no `__init__.py`

Em `providers/__init__.py`, adicione lazy import:

```python
with contextlib.suppress(ImportError):
    from observer.providers import groq_provider  # noqa: F401
```

### 3. Adicionar preços

Em `persistence.py`, atualize `PRICING`:

```python
PRICING: dict[tuple[str, str], tuple[float, float]] = {
    # ... providers existentes ...
    ("groq", "llama-3.3-70b"): (0.59, 0.79),
    ("groq", "llama-3.1-8b"): (0.05, 0.08),
    ("groq", "mixtral-8x7b"): (0.24, 0.24),
}
```

Preços em USD por 1M tokens (input, output). Consulte a [documentação oficial do Groq](https://groq.com/pricing) para valores atualizados.

### 4. Testes

`observer-framework/tests/test_groq_provider.py`:

```python
import json
from observer.providers.groq_provider import GroqProvider


class TestGroqProviderParse:
    def test_parse_json_with_singular_fix(self):
        provider = GroqProvider(api_key="", model="llama-3.3-70b-versatile")
        payload = json.dumps({
            "diagnosis": "erro de tipo",
            "root_cause": "variavel indefinida",
            "fix_description": "adicionar import",
            "fixed_code": "import pandas\n",
            "file_to_fix": "a.py",
            "confidence": 0.9,
            "requires_human_review": False,
        })
        data = provider._parse_json(payload)
        assert data["diagnosis"] == "erro de tipo"
        assert data["confidence"] == 0.9

    def test_parse_json_from_markdown_code_block(self):
        provider = GroqProvider(api_key="", model="llama-3.3-70b-versatile")
        payload = '```json\n{"diagnosis": "x", "confidence": 0.5}\n```'
        data = provider._parse_json(payload)
        assert data["diagnosis"] == "x"
```

### 5. Usar

```python
from observer.providers import create_llm_provider

llm = create_llm_provider(
    "groq",
    api_key=os.environ["GROQ_API_KEY"],
    model="llama-3.3-70b-versatile",
)
```

Ou via `observer_config.yaml`:

```yaml
observer:
  llm_provider: groq
  llm_model: llama-3.3-70b-versatile
```

---

## Adicionando um Git provider

Exemplo: provider para GitLab.

### 1. Criar o módulo

`providers/gitlab_provider.py`:

```python
"""Provider Git: GitLab (via python-gitlab)."""

from __future__ import annotations

import logging
from datetime import datetime

from observer.providers import register_git_provider
from observer.providers.base import (
    DiagnosisResult,
    GitProvider,
    PRResult,
    with_retry,
)

logger = logging.getLogger(__name__)


@register_git_provider("gitlab")
class GitLabProvider(GitProvider):
    """Cria branches e MRs no GitLab via python-gitlab."""

    def __init__(
        self,
        token: str = "",
        repo: str = "",  # formato: "group/project"
        base_branch: str = "develop",
        gitlab_url: str = "https://gitlab.com",
    ):
        self._token = token
        self._repo = repo
        self._base_branch = base_branch
        self._gitlab_url = gitlab_url

    @property
    def name(self) -> str:
        return "gitlab"

    @with_retry(max_retries=3, base_delay=2.0)
    def create_fix_pr(
        self,
        diagnosis: DiagnosisResult,
        failed_task: str,
    ) -> PRResult:
        try:
            import gitlab
        except ImportError as e:
            raise ImportError(
                "python-gitlab não instalado. Instale com: pip install python-gitlab"
            ) from e

        fixes = diagnosis.normalized_fixes()
        if not fixes:
            raise ValueError("DiagnosisResult sem fixes aplicaveis")

        gl = gitlab.Gitlab(self._gitlab_url, private_token=self._token)
        project = gl.projects.get(self._repo)

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        task_slug = failed_task.replace("_", "-")
        branch_name = f"fix/agent-auto-{task_slug}-{ts}"

        # Criar branch
        project.branches.create({
            "branch": branch_name,
            "ref": "main",
        })

        # Commits via Commits API (um commit agregado com múltiplas actions)
        actions = []
        for fix in fixes:
            actions.append({
                "action": "update",
                "file_path": fix["file_path"],
                "content": fix["code"],
            })

        project.commits.create({
            "branch": branch_name,
            "commit_message": (
                f"fix: correcao automatica em {failed_task}\n\n"
                f"{diagnosis.fix_description}"
            ),
            "actions": actions,
        })

        # Merge Request
        mr = project.mergerequests.create({
            "source_branch": branch_name,
            "target_branch": self._base_branch,
            "title": f"fix: [{failed_task}] correcao automatica",
            "description": (
                f"## Correcao Automatica — Observer Agent\n\n"
                f"**Confianca:** {diagnosis.confidence:.0%}\n\n"
                f"### Diagnostico\n{diagnosis.diagnosis}\n\n"
                f"### Causa Raiz\n{diagnosis.root_cause}\n\n"
                f"### Fix\n{diagnosis.fix_description}\n\n"
                f"🤖 Gerado por Observer Agent ({diagnosis.provider}/{diagnosis.model})"
            ),
        })

        return PRResult(
            pr_url=mr.web_url,
            pr_number=mr.iid,
            branch_name=branch_name,
        )

    def get_pr_status(self, pr_number: int) -> str:
        """Retorna o estado do merge request."""
        if not pr_number:
            return "unknown"
        try:
            import gitlab
        except ImportError:
            return "unknown"

        try:
            gl = gitlab.Gitlab(self._gitlab_url, private_token=self._token)
            project = gl.projects.get(self._repo)
            mr = project.mergerequests.get(pr_number)
            if mr.state == "merged":
                return "merged"
            if mr.state == "closed":
                return "closed"
            if mr.state == "opened":
                return "open"
            return "unknown"
        except Exception as exc:
            logger.warning(f"Falha ao consultar MR !{pr_number}: {exc}")
            return "unknown"
```

### 2. Registrar no `__init__.py`

```python
with contextlib.suppress(ImportError):
    from observer.providers import gitlab_provider  # noqa: F401
```

### 3. Usar

```yaml
observer:
  git_provider: gitlab
  base_branch: develop
```

```python
git = create_git_provider(
    "gitlab",
    token=os.environ["GITLAB_TOKEN"],
    repo="my-group/my-project",
    gitlab_url="https://gitlab.mycompany.com",
)
```

---

## Checklist para PR de um provider novo

- [ ] Classe implementa a ABC correspondente
- [ ] Decorator `@register_llm_provider` ou `@register_git_provider` aplicado
- [ ] Lazy import em `providers/__init__.py` dentro de `contextlib.suppress(ImportError)`
- [ ] Dependências novas mencionadas no README ou mantidas como opcionais
- [ ] Preços adicionados em `PRICING` (LLM)
- [ ] Testes unitários cobrem: parse de resposta, fallbacks, formato multi-file
- [ ] `ruff check` e `pytest` passam
- [ ] Exemplo de uso no README (opcional mas recomendado)
- [ ] Documentação do provider específico em `docs/` (opcional, útil se tem particularidades)

---

## Dicas

### `with_retry` no `diagnose`/`create_fix_pr`

Sempre use o decorator `@with_retry(max_retries=3, base_delay=2.0)` em chamadas externas. Ele ignora erros de lógica (`ValueError`, `KeyError`, `TypeError`, `ImportError`) e retenta apenas erros transientes.

### Lazy imports de dependências pesadas

Providers devem importar SDKs específicos (`anthropic`, `openai`, `PyGithub`, `python-gitlab`) dentro dos métodos, não no topo do módulo. Isso permite instalar o framework sem precisar de todos os SDKs:

```python
@with_retry(max_retries=3, base_delay=2.0)
def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise ImportError(
            "anthropic SDK não instalado. Instale com: pip install anthropic"
        ) from e
    # ...
```

### Compartilhando o `SYSTEM_PROMPT`

Para manter consistência entre providers, importe o prompt existente:

```python
from observer.providers.anthropic_provider import SYSTEM_PROMPT
```

Se seu provider precisa de um prompt diferente (ex: model tem token limit menor e precisa de prompt mais enxuto), define um localmente.

### Parse JSON resiliente

Todos os providers devem ter um `_parse_json(text)` com fallback para code blocks Markdown. Modelos menores frequentemente envolvem JSON em ` ```json ... ``` `:

```python
def _parse_json(self, text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return {
            "diagnosis": text[:500],
            "confidence": 0.3,
            "requires_human_review": True,
        }
```

### Propagando `fixes` no parse

Não esqueça de passar `fixes=data.get("fixes")` no constructor do `DiagnosisResult`. Sem isso, o suporte a multi-file não funciona no seu provider.
