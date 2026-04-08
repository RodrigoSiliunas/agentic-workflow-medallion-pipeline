# Product Guidelines

## Voice and Tone

- Conciso e direto
- Documentacao e comentarios em pt-BR
- Comentarios apenas onde a logica nao e auto-evidente
- Sem emojis, sem linguagem informal no codigo

## Design Principles

1. **Pragmatismo sobre perfeicao** — Entregar funcional primeiro, polir depois. Heuristica antes de ML. Simples antes de sofisticado.
2. **Fail-safe** — Falha em uma task nao corrompe dados (Delta ACID). Retry automatico. Rollback via Delta time travel.
3. **Idempotencia** — Qualquer etapa pode ser re-executada sem efeitos colaterais. Mesma entrada = mesma saida.
4. **Observabilidade** — Toda execucao gera metricas em Delta Table. Dashboard SQL. Alertas proativos. Emails em todos os cenarios (sucesso, correcao, falha).

## Architecture Principles

- **Separacao de responsabilidades**: Agente orquestra, notebooks processam, lib/ contem logica pura
- **Schema evolution**: Colunas novas aceitas via Delta `mergeSchema`, apenas obrigatorias validadas
- **Imutabilidade**: Bronze (Parquet cru) nunca alterado. Silver/Gold regeneraveis
- **Extensibilidade**: Nova tabela Gold = novo notebook + nova task no Workflow

## Data Sensitivity

- Dados sensiveis (CPF, email, telefone, placa) mascarados na Silver, nunca persistidos em claro
- `message_body` sofre redaction (substituicao de PII por versao mascarada)
- Chave HMAC obrigatoria via env var (`MASKING_SECRET`), sem fallback
- Acesso ao Bronze restrito via Unity Catalog
