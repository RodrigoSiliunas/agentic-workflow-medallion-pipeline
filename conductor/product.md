# Product Definition

## Project Name

agentic-workflow-medallion-pipeline

## Description

Pipeline agentico de transformacao de dados Medallion sobre conversas WhatsApp de vendas de seguro automotivo, rodando no Databricks + AWS.

## Problem Statement

Avaliar capacidade de construir um agente que cria, gerencia e mantem um pipeline de transformacao de dados como infraestrutura persistente, nao analises pontuais. O agente deve ser autonomo: detectar falhas, corrigir, e notificar.

## Target Users

Avaliadores do teste tecnico de Data & AI Engineering — demonstrar competencia em engenharia de dados, agentes autonomos e Databricks.

## Key Goals

1. **Pipeline Medallion funcional e autonomo no Databricks + AWS** — Bronze (ingestao + schema evolution), Silver (dedup, extracao, mascaramento, redaction), Gold (12 tabelas analiticas)
2. **Agente que auto-monitora, auto-corrige e notifica via email** — Task 0 (pre-check) + Task 5 (post-check, recovery, rollback Delta, guardrails, notificacoes)
3. **Insights criativos na Gold layer** — Funil com gargalos, scoring de agentes, inteligencia competitiva, lead scoring, churn/reengajamento, first contact resolution, etc.

## Domain Context

- **Dados**: ~15k conversas WhatsApp, 153k mensagens, vendas de seguro automotivo, pt-BR
- **Periodo**: Fevereiro 2026
- **Imperfeicoes intencionais**: nomes inconsistentes, dados sensiveis em texto livre, duplicatas sent+delivered, transcricoes de audio com erros
- **Referencia**: `analise_arquitetural/analise.md` contem o design completo
