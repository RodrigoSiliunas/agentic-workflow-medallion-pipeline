"""Contract tests shared fixtures (T7 F5).

Integração com VCR.py fica documentada aqui. Quando `vcrpy` estiver
disponível + chave de API para gravação, a fixture `vcr_config` abaixo
será ativada pra gravar cassettes sanitizados.

Até lá, os testes em `tests/contracts/` usam fakes estruturais —
mesma forma de resposta, sem chamada externa. Isso garante que o
contrato da interface `ChatLLMProvider` / `LLMProvider` não quebra,
mesmo sem rede.

## Habilitando VCR (quando pronto)

1. `pip install vcrpy`
2. Criar diretório `tests/contracts/cassettes/`
3. Exportar `ANTHROPIC_API_KEY=sk-...` (conta dedicada de teste)
4. Descomentar o bloco abaixo.
5. `pytest tests/contracts/ --vcr-record=new_episodes` (primeira run)
6. `pytest tests/contracts/` (runs seguintes usam cassettes gravados)

Os cassettes gravados ficam no repo após manual review garantir que
os campos `Authorization`, `x-api-key` e `anthropic-api-key` saíram
dos headers (`filter_headers`).
"""

from __future__ import annotations

# pytest fixtures + pytest_vcr (opt-in, quando vcrpy disponível)
#
# import pytest
# import vcr
#
# @pytest.fixture(scope="module")
# def vcr_config():
#     return {
#         "filter_headers": [
#             "authorization",
#             "x-api-key",
#             "anthropic-api-key",
#             "cookie",
#         ],
#         "record_mode": "new_episodes",
#         "match_on": ["method", "uri", "body"],
#         "cassette_library_dir": "tests/contracts/cassettes",
#     }
