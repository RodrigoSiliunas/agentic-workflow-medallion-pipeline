"""Database seed — popula tabelas com dados iniciais.

Chamado no lifespan do FastAPI quando AUTO_SEED=True. Idempotente:
se o template ja existe (por slug), apenas atualiza; senao, insere.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template

logger = structlog.get_logger()


TEMPLATE_SEEDS = [
    {
        "slug": "pipeline-seguradora-whatsapp",
        "name": "Pipeline Seguradora WhatsApp",
        "tagline": "Medallion ETL para conversas WhatsApp de seguro auto",
        "description": (
            "Pipeline Medallion (Bronze \u2192 Silver \u2192 Gold) sobre conversas WhatsApp de "
            "seguradora, com mascaramento PII, 12 tabelas analiticas e Observer Agent autonomo "
            "que corrige bugs via PRs no GitHub."
        ),
        "category": "ETL",
        "tags": ["whatsapp", "seguros", "etl", "medallion", "pii", "observer"],
        "icon": "chat-bubble-left-right",
        "icon_bg": "#22c55e",
        "version": "1.3.0",
        "author": "Namastex Labs",
        "deploy_count": 47,
        "duration_estimate": "8-12 min",
        "architecture_bullets": [
            "Bronze ingestion: S3 parquet -> Delta Lake (overwrite idempotente)",
            "Silver: dedup + mascaramento PII (HMAC) + enrichment conversacional",
            "Gold: 12 tabelas analiticas (funnel, sentiment, NPS, handle_time)",
            "Validation gate: row counts, nulls, consistency",
            "Observer Agent: Claude Opus diagnostica falhas + cria PR no GitHub",
        ],
        "env_schema": [
            {
                "key": "catalog_name",
                "label": "Unity Catalog name",
                "type": "text",
                "required": True,
                "placeholder": "medallion",
                "default": "medallion",
                "helper": "Catalog principal que vai abrigar os schemas bronze/silver/gold",
            },
            {
                "key": "s3_bucket",
                "label": "S3 bucket name",
                "type": "text",
                "required": True,
                "placeholder": "namastex-medallion-datalake",
                "helper": "Bucket que vai receber os parquets ingeridos",
            },
            {
                "key": "schedule_cron",
                "label": "Schedule (cron expression)",
                "type": "cron",
                "required": False,
                "placeholder": "0 6 * * *",
                "default": "0 6 * * *",
                "helper": "Cron em timezone America/Sao_Paulo. Vazio = sem schedule",
            },
            {
                "key": "masking_secret",
                "label": "PII masking secret (HMAC)",
                "type": "password",
                "required": True,
                "helper": "Chave HMAC usada para mascarar CPF, telefone, email",
            },
        ],
        "changelog": [
            {
                "version": "1.3.0",
                "date": "2026-04-10",
                "changes": [
                    "Observer agora usa trigger automatico via task sentinel",
                    "Dedup de diagnosticos via cache Delta",
                    "Multi-file fixes suportados",
                ],
            },
            {
                "version": "1.2.0",
                "date": "2026-03-22",
                "changes": [
                    "Observer feedback loop via GitHub Action",
                    "Validacao pre-PR com ruff + pytest",
                ],
            },
            {
                "version": "1.1.0",
                "date": "2026-02-15",
                "changes": ["Mascaramento HMAC obrigatorio", "Schema evolution via mergeSchema"],
            },
        ],
        "published": True,
    },
    {
        "slug": "pipeline-crm-sap",
        "name": "Pipeline CRM SAP",
        "tagline": "Ingestao incremental de Accounts, Opportunities e Contacts do SAP",
        "description": (
            "Pipeline que conecta ao SAP via OData, faz CDC incremental das entidades de CRM "
            "(Accounts, Opportunities, Contacts, Activities), normaliza schemas e materializa "
            "views analiticas prontas para o time de vendas."
        ),
        "category": "CRM",
        "tags": ["sap", "crm", "cdc", "odata", "vendas"],
        "icon": "building-office-2",
        "icon_bg": "#3b82f6",
        "version": "0.9.0",
        "author": "Namastex Labs",
        "deploy_count": 12,
        "duration_estimate": "6-9 min",
        "architecture_bullets": [
            "CDC incremental via OData com high-watermark por entidade",
            "Bronze: payloads brutos particionados por data",
            "Silver: normalizacao + deduplicacao por business key",
            "Gold: Accounts 360, Funnel de Opportunities, Activity heatmap",
            "Retry com backoff exponencial em falhas do SAP",
        ],
        "env_schema": [
            {
                "key": "sap_host",
                "label": "SAP OData endpoint",
                "type": "url",
                "required": True,
                "placeholder": "https://sap.empresa.com.br/sap/opu/odata",
            },
            {"key": "sap_user", "label": "SAP username", "type": "text", "required": True},
            {
                "key": "sap_password",
                "label": "SAP password",
                "type": "password",
                "required": True,
            },
            {
                "key": "entities",
                "label": "Entidades a sincronizar",
                "type": "text",
                "required": True,
                "default": "Accounts,Opportunities,Contacts,Activities",
                "helper": "Lista separada por virgula",
            },
            {
                "key": "schedule_cron",
                "label": "Schedule",
                "type": "cron",
                "required": False,
                "default": "0 */4 * * *",
                "helper": "Default: a cada 4 horas",
            },
        ],
        "changelog": [
            {
                "version": "0.9.0",
                "date": "2026-04-02",
                "changes": [
                    "Beta publico",
                    "Suporte a 4 entidades core",
                    "Gold: Accounts 360 view",
                ],
            },
        ],
        "published": True,
    },
    {
        "slug": "pipeline-ecommerce-hotmart",
        "name": "Pipeline E-commerce Hotmart",
        "tagline": "Eventos de checkout, pagamento e entrega da API Hotmart",
        "description": (
            "Consome webhooks da Hotmart (purchase, subscription, refund) em streaming, "
            "materializa funil de conversao e cohort de recompra. Inclui alertas de anomalia "
            "em tempo real via Observer."
        ),
        "category": "E-commerce",
        "tags": ["hotmart", "e-commerce", "streaming", "webhooks", "cohort"],
        "icon": "shopping-cart",
        "icon_bg": "#ef4444",
        "version": "0.6.0",
        "author": "Namastex Labs",
        "deploy_count": 5,
        "duration_estimate": "7-10 min",
        "architecture_bullets": [
            "Webhook receiver -> Kinesis -> Delta streaming",
            "Silver: normalizacao de eventos (purchase, subscription, refund, chargeback)",
            "Gold: Funnel de checkout, Cohort de recompra, LTV por produto",
            "Observer monitora anomalia em refund_rate e dispara alerta",
        ],
        "env_schema": [
            {
                "key": "hotmart_client_id",
                "label": "Hotmart Client ID",
                "type": "text",
                "required": True,
            },
            {
                "key": "hotmart_client_secret",
                "label": "Hotmart Client Secret",
                "type": "password",
                "required": True,
            },
            {
                "key": "kinesis_stream",
                "label": "Kinesis stream name",
                "type": "text",
                "required": True,
                "default": "hotmart-events",
            },
            {
                "key": "refund_alert_threshold",
                "label": "Refund rate alert (%)",
                "type": "text",
                "required": False,
                "default": "5",
                "helper": "Dispara alerta se refund_rate > threshold em 24h",
            },
        ],
        "changelog": [
            {
                "version": "0.6.0",
                "date": "2026-03-28",
                "changes": [
                    "Primeiro release beta",
                    "Cohort de recompra",
                    "LTV por produto",
                ],
            },
        ],
        "published": True,
    },
]


async def seed_templates(db: AsyncSession) -> int:
    """Insere os 3 templates fixos. Idempotente: skip se ja existe."""
    inserted = 0
    for data in TEMPLATE_SEEDS:
        existing = await db.execute(select(Template).where(Template.slug == data["slug"]))
        if existing.scalar_one_or_none():
            continue
        db.add(Template(**data))
        inserted += 1
    await db.commit()
    if inserted:
        logger.info("templates seeded", count=inserted)
    return inserted
