# ADR 0003 — LLM/Git provider consolidation

**Status**: accepted · **Data**: 2026-04-16 · **Track**: T7

## Contexto

O repo tem dois módulos independentes que conversam com LLMs e com o Git:

- `observer-framework/observer/providers/` — abstração pluggable com
  `LLMProvider`, `GitProvider`, factory + decorators `@register_llm_provider`.
  Providers implementados: `anthropic`, `openai`, `github`. Retry com
  backoff, testes 113+.
- `platform/backend/app/services/llm_orchestrator.py` — 401 LOC
  instanciando `anthropic.AsyncAnthropic` diretamente, com lógica de
  tool calling própria. Zero reuso com o observer.

Consequências observadas:

1. **Bug fix aplicado 2 vezes** — prompt injection hardening (T1)
   protegeu observer mas backend continua vulnerável.
2. **Retry policy drift** — observer usa `with_retry(3, 2.0)`; backend
   não tem retry de rede em algumas call sites.
3. **Testes duplicados** — 113 observer tests + backend mocks exercitam
   os mesmos conceitos (parsing de resposta JSON, fallback, usage
   tracking).
4. **Bloqueia extração do observer-framework como pacote standalone**
   porque o repo privado `RodrigoSiliunas/observer` não teria consumidor
   real; T7 precisa decidir se/como o backend vira cliente.

## Opções

### Option A — Publicar `observer` como pacote Python

`observer-framework/` vira package instalável (PyPI ou GitHub
Packages). Backend adiciona `observer>=X` como dependência e usa
`create_llm_provider("anthropic", api_key=...)` + tool registry no
lugar de `anthropic.AsyncAnthropic` direto.

Pros:
- Hardening da T1 (XML tagging, allowlist de paths, redaction, import
  validator) passa a proteger o backend sem duplicação.
- Retry + factory pattern compartilhados.
- `observer-framework` ganha consumidor real que valida a API pública.
- Caminho direto para extrair pro repo `RodrigoSiliunas/observer`
  quando o produto for open-source.

Cons:
- Exige versionamento disciplinado (SemVer) — breaking change em
  providers afeta backend.
- Release coordenado com deploy do backend.
- PyPI publish + CI pipeline novo (ou `pip install git+https://...`
  como solução tático-curta).

### Option B — Terceiro pacote `providers-core`

Extração mais radical: cria `providers-core` que vira dependência
TANTO do observer-framework quanto do backend. Cada consumidor herda
só o que precisa.

Pros:
- Dependência assimétrica evitada (backend não depende de código que
  lê notebooks Databricks).
- Boundary arquitetural mais limpo.

Cons:
- Custo de maintainence 3× (3 pacotes versus 2).
- Falta de consumidor primário — providers-core sempre meia-abstração.
- Overengineering para o tamanho atual do projeto.
- Discovery do código fica difícil (onde corrigir bug?).

### Option C — Manter separado, documentar divergência

Aceitar a duplicação como intencional. Cada módulo segue evolução
própria; T1 hardening é reaplicado quando fizer sentido.

Pros:
- Zero refactor.
- Deploys independentes.

Cons:
- T1 fica vulnerável no backend indefinidamente.
- Drift acumula; futuro refactor fica mais caro.
- Bloqueia visão do observer como produto standalone.

## Decisão

**Option A** — publicar `observer` como pacote e o backend passa a
consumir. Racional:

1. T1 já provou que hardening é caro de reaplicar em dois lugares.
2. Observer-framework tem API pública bem definida (factory +
   dataclasses) — passar para pacote é empacotamento, não refactor.
3. Produto caminha para open-source do observer-framework; um
   consumidor real (backend) é vantagem, não custo.
4. Custo de Option B (3 pacotes) só paga após escalar — hoje temos
   um produto. YAGNI.

## Escopo da implementação (fases T7)

Sequencial, cada fase é mergeável isoladamente:

1. **Phase 1** — empacotar observer-framework: `pyproject.toml` com
   `name = "observer"`, `version = "0.9.0"`, publish workflow em
   `.github/workflows/publish-observer.yml` via tag `observer-v*`.
   Target de publish: GitHub Packages inicialmente (evita burocracia
   PyPI); migração para PyPI fica para v1.0.0.

2. **Phase 2** — backend consome: `platform/backend/pyproject.toml`
   ganha `observer` como dep. `llm_orchestrator.py` substitui
   `anthropic.AsyncAnthropic` direto por
   `create_llm_provider("anthropic", …)`. Testes backend continuam
   passando.

3. **Phase 3** — `TOOL_REGISTRY` extraído pra
   `platform/backend/app/services/tools/` — um arquivo por tool +
   decorator `@register_tool`. Facilita adicionar tool novo sem tocar
   no orchestrator.

4. **Phase 4** (independente das anteriores — pode ir antes) —
   `DatabricksService` ganha singleton `httpx.AsyncClient` via
   `@classmethod _shared_client()` (pattern de `OmniService`) +
   `asyncio.gather` em `get_table_schemas`. Win de performance sem
   depender da decisão Option A.

5. **Phase 5** — contract tests com VCR.py em
   `observer-framework/tests/contracts/`. Cassettes sanitizados
   (sem API keys). Backend reusa via pytest plugin.

## Riscos mitigados

- **Versionamento** — SemVer estrito, release notes por versão,
  CHANGELOG mantido. Breaking changes entram em major (`1.x`).
- **API keys em cassettes VCR** — `filter_headers=["authorization",
  "x-api-key"]` + review manual antes de commit.
- **Release coordenado** — backend tem `observer>=X.Y,<Z` no
  pyproject pra travar major; minor/patch atualizam livremente.

## Consequências

- Observer-framework vira pacote com CI de publish.
- Backend reduz ~200 LOC (`llm_orchestrator.py` menor, tools extraídos).
- T1 hardening passa a proteger todas as chamadas a Anthropic.
- Extração futura pro repo standalone fica trivial.

## Revisão

Reavaliar em 12 meses (~2027-04):
- Número de versões publicadas e frequência de breaking changes.
- Consumidores externos além do backend surgiram?
- Migrou pra PyPI? Precisa ainda?
- Considerar Option B se surgir 3º consumidor com requisitos
  muito diferentes.
