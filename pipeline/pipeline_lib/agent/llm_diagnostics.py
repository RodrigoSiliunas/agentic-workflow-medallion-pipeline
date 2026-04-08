"""Modulo de diagnostico de erros via Claude API.

Analisa stack traces, codigo e contexto do pipeline para propor correcoes.
"""

import json
import os

import anthropic


def get_client() -> anthropic.Anthropic:
    """Cria cliente Anthropic. Falha se chave nao configurada."""
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def diagnose_error(
    error_message: str,
    stack_trace: str,
    failed_task: str,
    notebook_code: str,
    schema_info: str,
    pipeline_state: dict,
) -> dict:
    """Envia contexto do erro para Claude e recebe diagnostico + correcao.

    Retorna dict com: diagnosis, root_cause, fix_description, fixed_code, confidence.
    """
    client = get_client()

    system_prompt = """Voce e um engenheiro de dados senior especializado em PySpark, Delta Lake e Databricks.
Seu trabalho e diagnosticar erros em pipelines de dados e propor correcoes de codigo.

Regras:
- Responda SEMPRE em JSON valido
- Seja especifico sobre a causa raiz
- Proponha codigo corrigido que resolva o problema
- Indique seu nivel de confianca (0.0 a 1.0)
- Se nao tiver certeza, diga e sugira investigacao adicional
- NUNCA invente informacoes sobre o schema ou dados"""

    user_prompt = f"""O pipeline Medallion falhou. Preciso de diagnostico e correcao.

## Task que falhou
{failed_task}

## Erro
{error_message}

## Stack Trace
{stack_trace}

## Codigo do notebook que falhou
```python
{notebook_code}
```

## Schema das tabelas (Unity Catalog)
{schema_info}

## Estado do pipeline
{json.dumps(pipeline_state, indent=2)}

## Responda em JSON com esta estrutura:
{{
    "diagnosis": "Descricao clara do que aconteceu",
    "root_cause": "Causa raiz tecnica",
    "fix_description": "O que precisa ser alterado e por que",
    "fixed_code": "Codigo completo do notebook corrigido (ou null se nao aplicavel)",
    "file_to_fix": "Path do arquivo a corrigir (ex: notebooks/silver/dedup_clean.py)",
    "confidence": 0.0-1.0,
    "requires_human_review": true/false,
    "additional_notes": "Notas extras ou investigacoes sugeridas"
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extrair JSON da resposta
    text = response.content[0].text
    try:
        # Tentar parsear JSON direto
        result = json.loads(text)
    except json.JSONDecodeError:
        # Tentar extrair JSON de dentro de markdown code block
        import re

        json_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
        else:
            result = {
                "diagnosis": text,
                "root_cause": "Nao foi possivel parsear resposta estruturada",
                "fix_description": text,
                "fixed_code": None,
                "file_to_fix": None,
                "confidence": 0.3,
                "requires_human_review": True,
                "additional_notes": "Resposta do LLM nao estava em JSON",
            }

    return result
