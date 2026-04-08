# Workflow

## TDD Policy

**Moderado**: Testes obrigatorios para `lib/` (extratores, masking, schema validation). Flexivel para notebooks Databricks (testados via execucao no workspace).

- Extratores: cada regex deve ter testes com exemplos reais do dataset
- Masking: testes de formato preservado, determinismo, e chave obrigatoria
- Schema: testes de colunas obrigatorias, colunas novas, e tipos

## Commit Strategy

**Conventional Commits em pt-BR**:

```
feat: adiciona extrator de CPF com validacao de digitos
fix: corrige regex de placa Mercosul para aceitar formato sem hifen
refactor: desacopla Silver em 3 tasks independentes
test: adiciona testes para mascaramento de email
docs: atualiza README com instrucoes de setup Databricks
```

## Code Review

**Opcional / self-review** — projeto solo para teste tecnico. Revisao propria antes de commit.

## Verification Checkpoints

Verificacao manual apos cada **fase do plano de implementacao**:

| Fase | Checkpoint |
|------|-----------|
| **Fase 1** (Infra + Bronze) | Dados no S3, Delta Table Bronze no Unity Catalog, notebook funcional |
| **Fase 2** (Silver) | 3 tasks Silver funcionais, dados mascarados, message_body redacted |
| **Fase 3** (Gold) | 12 tabelas Gold populadas, insights coerentes |
| **Fase 4** (Agente + Workflow) | Workflow rodando 1x/dia, agent_pre + agent_post funcionais, emails enviados |
| **Fase 5** (Diferenciais) | ML sentiment, testes CI, README completo |

## Task Lifecycle

1. **Criacao**: Track definida com spec + plan
2. **Implementacao**: Seguir plano fase a fase
3. **Verificacao**: Checkpoint ao final de cada fase
4. **Conclusao**: Track marcada como completa

## Branch Strategy

- `main` — branch principal, sempre funcional
- `feat/<track-id>` — branch por track de feature
- Merge para main apos checkpoint passar
