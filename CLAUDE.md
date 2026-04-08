# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Data & AI Engineering technical test** — building an agentic data transformation pipeline using the Medallion architecture (Bronze → Silver → Gold) over WhatsApp sales conversation data for auto insurance.

**Key constraint**: The agent must build the pipeline as **persistent infrastructure** (like a Databricks job), NOT perform one-off analyses. The agent must self-manage: detect failures, alert, and auto-correct.

## Source Data

- **File**: `conversations_bronze.parquet` — ~15k conversations, 120-150k messages
- **Period**: Feb 2026
- **Domain**: WhatsApp conversations between human sales agents and leads for auto insurance
- **Language**: Brazilian Portuguese (pt-BR)

### Data Characteristics (intentional imperfections)
- `sender_name`: inconsistent casing, abbreviations, accents, empty values for the same lead
- `message_body`: unstructured text containing CPF, CEP, email, phone, plates in varied formats
- `status`: duplicate rows (sent + delivered) for same message
- `message_type=audio`: transcriptions with speech recognition errors
- `message_type=sticker/image`: empty/null `message_body`
- Vehicle data in free text, unordered ("gol 2019 1.0 placa ABC1D23")
- Competitor insurer mentions in informal language
- `metadata` column: JSON string with `device`, `city`, `state`, `response_time_sec`, `is_business_hours`, `lead_source`

### Key Columns
- `conversation_id` (conv_XXXXXXXX): groups all messages in one conversation
- `direction`: outbound (seller) / inbound (lead) — seller always starts
- `conversation_outcome`: venda_fechada | perdido_preco | perdido_concorrente | ghosting | desistencia_lead | proposta_enviada | em_negociacao
- `campaign_id`: 8-10 campaigns, same value across all messages in a conversation
- `agent_id`: 15-20 sellers with uneven distribution

## Pipeline Requirements

### Bronze Layer
- Raw data as-is from `conversations_bronze.parquet`
- Unstructured messages + conversation metadata

### Silver Layer
- Clean and organize data per user/lead
- Extract structured info from messages: emails, CPF, phone, plates, vehicle data, CEP
- Deduplicate status rows (sent+delivered)
- Normalize names, remove noise
- **Sensitive data must be masked** preserving original dimensions

### Gold Layer
- Analytical tables with classifications and groupings
- Must **auto-update** when new data arrives in Bronze
- Expected insights: email provider distribution, persona/profile classification, audience segmentation, customer sentiment analysis
- Creativity encouraged — go beyond the suggested examples

### Agent Requirements
- Pure Python implementation
- Agent creates AND manages the pipeline (self-correction on failure)
- Live pipeline: Gold auto-updates when Bronze source grows
- Code in a public GitHub repository
- **Differentiator**: Databricks integration (free tier)

## Conversation Distribution
- ~35% cold lead/bounce (2-4 messages)
- ~30% short conversation (5-10 messages)
- ~25% medium conversation (11-20 messages)
- ~10% long conversation (21-30+ messages)
