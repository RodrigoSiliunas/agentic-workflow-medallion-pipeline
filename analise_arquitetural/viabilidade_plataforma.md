# Analise de Viabilidade Tecnica -- Plataforma Conversacional Integrada ao Pipeline Medallion

## 1. Resumo Executivo

**Veredicto: Viavel, com ressalvas importantes.**

O pipeline atual (`agentic-workflow-medallion-pipeline`) possui uma base solida para integracao com uma plataforma conversacional: arquitetura Medallion bem definida com 8 tasks no Databricks Workflow, agente autonomo com pre/post-check, 89 testes unitarios na `pipeline_lib/`, deploy automatizado via scripts Python, e CI no GitHub Actions. A infraestrutura de estado ja existe (`medallion.pipeline.state`, `notifications`, `metrics`), o que facilita a exposicao de contexto para um LLM.

**Porem, a complexidade nao e trivial.** O sistema atual opera como batch diario isolado -- nao ha APIs HTTP, nao ha webhooks de saida, e a comunicacao entre tasks usa exclusivamente `dbutils.jobs.taskValues` (acoplamento forte ao runtime Databricks). Transformar isso em um sistema que responde a interacoes humanas em tempo real exige uma camada intermediaria significativa.

**Esforco estimado:**
- Fase 1 (LLM diagnostics + auto-PR): **Ja implementado** neste projeto
- Fase 2 (Web platform MVP): 4-6 semanas, 1-2 engenheiros
- Fase 3 (Multi-channel via Omni): 3-4 semanas, 1 engenheiro
- Fase 4 (Features avancadas): ongoing

---

## 2. Viabilidade por Feature

### 2.1 LLM Agent que Diagnostica Erros e Propoe Code Fixes

**Viabilidade: ALTA ✅ Implementado**

Implementado em `pipeline_lib/agent/llm_diagnostics.py` e integrado ao `agent_post.py`. Claude API recebe: stack trace, codigo do notebook, schema das tabelas, estado do pipeline. Retorna: diagnostico, causa raiz, codigo corrigido, confianca.

**Riscos:**
- **Alucinacao de codigo**: Mitigacao via CI obrigatorio (ruff + pytest) + review humano
- **Contexto insuficiente**: Budget de ~25k-35k tokens para diagnostico completo
- **Tempo de resposta**: 30-60s aceitavel para batch diario

### 2.2 Auto-Geracao de GitHub PRs

**Viabilidade: ALTA ✅ Implementado**

Implementado em `pipeline_lib/agent/github_pr.py`. Cria branch `fix/agent-auto-{task}-{timestamp}`, commita o fix, abre PR com descricao completa (diagnostico, confianca, emoji de severidade).

**Regras:** Branch a partir de `main`, maximo 1 PR por run, review humano obrigatorio.

### 2.3 Notificacoes por Email com Diagnostico + Link do PR

**Viabilidade: ALTA ✅ Estrutura pronta**

`agent_post.py` ja gera o corpo do email via `build_ai_notification_body()`. Falta conectar ao transporte (AWS SES ou SendGrid) quando a conta AWS desbloquear.

### 2.4 Interface Web de Chat com Contexto do Pipeline

**Viabilidade: MEDIA-ALTA (esforco significativo, 4-6 semanas)**

Nao existe infraestrutura web no projeto atual. Requer: FastAPI backend, React frontend, auth, context management com Redis.

### 2.5 Multi-Channel (WhatsApp/Discord/Telegram via Omni)

**Viabilidade: MEDIA (3-4 semanas, dependencia externa)**

Depende da maturidade do [Omni](https://github.com/automagik-dev/omni). Mitigacao: `ChannelAdapter` interface para abstrair a dependencia.

### 2.6 Contexto Compartilhado Entre Conversas

**Viabilidade: MEDIA (desafio de token management)**

Estrategia de 3 niveis de contexto:

| Nivel | Quando | Tokens | Custo/chamada |
|-------|--------|--------|---------------|
| 1. Resumo | Toda interacao | ~800 | ~$0.01 |
| 2. Detalhes | Pergunta especifica | ~3k-8k | ~$0.05 |
| 3. Completo | Diagnostico com fix | ~25k-35k | ~$0.50-0.70 |

---

## 3. Requisitos Tecnicos para Integracao

### 3.1 O que ja existe no codebase (pronto para integrar)

| Componente | Arquivo | O que faz |
|------------|---------|-----------|
| LLM Diagnostics | `pipeline_lib/agent/llm_diagnostics.py` | Envia contexto para Claude, recebe diagnostico JSON |
| GitHub PR | `pipeline_lib/agent/github_pr.py` | Cria branch + commit + PR automatico |
| Agent Post | `notebooks/agent_post.py` | Orquestra: detecta falha → rollback → LLM → PR → email |
| Estado | `medallion.pipeline.state` | Historico de execucoes (Delta Table) |
| Metricas | `medallion.pipeline.metrics` | Rows processadas, duracao, erros por task |
| Notificacoes | `medallion.pipeline.notifications` | Log de todos os emails/alertas |
| Validacao | `notebooks/validation/checks.py` | Quality checks com resultados estruturados |

### 3.2 O que a Platform API precisara consumir

| Dado | Fonte | Como acessar |
|------|-------|-------------|
| Status do pipeline | `medallion.pipeline.state` | Databricks SDK → `spark.table()` |
| Metricas | `medallion.pipeline.metrics` | Databricks SDK |
| Notificacoes/emails | `medallion.pipeline.notifications` | Databricks SDK |
| Schemas das tabelas | Unity Catalog | `DESCRIBE TABLE` via SQL |
| Codigo dos notebooks | GitHub API | `repo.get_contents()` |
| Historico de runs | Databricks Jobs API | `w.jobs.list_runs()` |
| Dados Gold (amostra) | Unity Catalog | `SELECT * LIMIT 10` |

### 3.3 Webhook de saida (adicionar ao agent_post.py)

Para que a Platform API receba eventos em tempo real, adicionar webhook HTTP:

```python
def emit_webhook(event_type: str, payload: dict):
    """Envia evento para Platform API."""
    import requests
    webhook_url = spark.conf.get("pipeline.webhook_url", "")
    if webhook_url:
        requests.post(webhook_url, json={
            "event": event_type,
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "payload": payload,
        }, timeout=10)
```

### 3.4 Seguranca

- **Dados PII**: Silver/Gold ja mascarados via `pipeline_lib/masking/`. LLM nunca recebe Bronze.
- **Codigo**: LLM propoe via PR, nunca executa diretamente. CI + review humano obrigatorios.
- **Secrets**: Databricks Secrets + AWS Secrets Manager (nunca hardcoded)
- **Multi-tenant** (futuro): JWT com `org_id`, row-level security via Unity Catalog

---

## 4. Arquitetura de Integracao

```
ESTADO ATUAL (ja funciona)                 FUTURO (plataforma)
+---------------------------+              +---------------------------+
| Databricks Workflow       |              | Platform API (FastAPI)    |
|                           |   webhook    |                           |
| agent_post.py -------->  |------------->| /webhook/pipeline-event   |
|   detecta falha           |              |   |                       |
|   rollback Delta          |              |   v                       |
|   Claude API diagnostica  |              | Context Builder           |
|   cria PR no GitHub       |              |   |                       |
|   persiste notificacao    |              |   v                       |
|                           |              | Chat Engine               |
| pipeline.state            |  SDK query   |   |                       |
| pipeline.metrics   <------|<-------------| Databricks SDK            |
| pipeline.notifications    |              |                           |
+---------------------------+              +---------------------------+
                                                    |
                                           +--------|--------+
                                           |        |        |
                                           v        v        v
                                         Web    WhatsApp  Discord
                                         Chat   (Omni)   (Omni)
```

### Fluxo atual (implementado):
```
Pipeline falha → Rollback → Claude API → PR no GitHub → Email
```

### Fluxo futuro (com plataforma):
```
Pipeline falha → Rollback → Claude API → PR → Email
                                            → Webhook → Platform API
                                            → Chat: "Pipeline falhou, PR #42 criado"
                                            → WhatsApp: "Alerta: pipeline com erro"
Usuario no chat: "o que aconteceu?"
                → Platform API → Context Builder → Claude → Resposta
```

---

## 5. Riscos e Mitigacoes

| Risco | Severidade | Probabilidade | Mitigacao |
|-------|------------|---------------|-----------|
| **LLM alucina codigo** | Alta | Media | CI obrigatorio + review humano + sandbox |
| **Token limits** | Media | Alta | 3 niveis de contexto + sumarizacao |
| **Custo API Anthropic** | Media | Certa | Sonnet para simples, Opus para diagnostico |
| **LLM ve dados sensiveis** | Alta | Baixa | Silver/Gold mascarados, nunca Bronze |
| **Omni instavel** | Media | Media | ChannelAdapter interface abstrai |
| **WhatsApp API complexa** | Media | Media | Aprovacao Meta + templates + custo |
| **Complexidade operacional** | Alta | Alta | Avanco incremental, validar cada fase |

---

## 6. Roadmap

| Fase | Descricao | Esforco | Status |
|------|-----------|---------|--------|
| 1 | LLM Diagnostics + Auto-PR | 2-3 semanas | ✅ Implementado |
| 2 | Web Platform MVP (chat + auth) | 4-6 semanas | Proximo |
| 3 | Multi-channel (Omni) | 3-4 semanas | Futuro |
| 4 | Features avancadas | Ongoing | Futuro |

---

## 7. Estimativa de Custo Mensal

| Componente | Fase 1 | Fase 2 | Fase 3 |
|------------|--------|--------|--------|
| Anthropic API | $20 | $45 | $60 |
| AWS Infra (ECS/Redis/ALB) | $0 | $50 | $60 |
| Databricks (SQL Warehouse) | $0 | $20 | $20 |
| WhatsApp Business | $0 | $0 | $15 |
| **Total** | **$20** | **$115** | **$155** |

---

## 8. Conclusao

**Fase 1 ja implementada.** O agente de IA com Claude API + auto-PR esta no codigo, pronto para testar quando a AWS desbloquear.

**Proximo passo**: Web Platform MVP (Fase 2). O documento `plataforma_conversacional_spec.md` contera as especificacoes tecnicas detalhadas para construir essa plataforma.

**Recomendacao**: avance incrementalmente, valide cada fase antes de iniciar a proxima. O pipeline atual ja e robusto — a plataforma conversacional deve amplificar sua utilidade, nao comprometer sua estabilidade.
