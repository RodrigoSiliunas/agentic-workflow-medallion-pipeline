"""Database seed — popula tabelas com dados iniciais.

Chamado no lifespan do FastAPI quando AUTO_SEED=True. Idempotente:
se o template ja existe (por slug), apenas atualiza; senao, insere.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.company import Company
from app.models.pipeline import Pipeline
from app.models.template import Template
from app.models.user import User

logger = structlog.get_logger()


# Tenant de demonstracao reproduzivel. Gate atras de SEED_DEMO_TENANT (default off).
DEMO_COMPANY_SLUG = "acme"
DEMO_COMPANY_NAME = "Acme Seguros"
DEMO_ADMIN_EMAIL = "admin@acme.com"
DEMO_ADMIN_NAME = "Admin Acme"
DEMO_ADMIN_PASSWORD = "supersecret1"  # noqa: S105 — credencial de demo, nunca em prod
DEMO_PIPELINE_NAME = "Seguradora WhatsApp"
DEMO_PIPELINE_DESCRIPTION = "Medallion ETL WhatsApp"
DEMO_PIPELINE_GITHUB_REPO = "RodrigoSiliunas/agentic-workflow-medallion-pipeline"
DEMO_PIPELINE_TEMPLATE_SLUG = "pipeline-seguradora-whatsapp"


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
        "author": "Flowertex Labs",
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
                "group": "main",
            },
            {
                "key": "s3_bucket",
                "label": "S3 bucket name (datalake)",
                "type": "text",
                "required": True,
                "placeholder": "flowertex-medallion-datalake",
                "helper": (
                    "Bucket dos parquets ingeridos. "
                    "Root bucket sera derivado como '{nome}-root'."
                ),
                "group": "main",
            },
            {
                "key": "schedule_cron",
                "label": "Schedule (cron expression)",
                "type": "cron",
                "required": False,
                "placeholder": "0 6 * * *",
                "default": "0 6 * * *",
                "helper": "Cron em timezone America/Sao_Paulo. Vazio = sem schedule",
                "group": "main",
            },
            {
                "key": "masking_secret",
                "label": "PII masking secret (HMAC)",
                "type": "password",
                "required": True,
                "helper": "Chave HMAC usada para mascarar CPF, telefone, email",
                "group": "main",
            },
            {
                "key": "cluster_id",
                "label": "Cluster ID (opcional)",
                "type": "text",
                "required": False,
                "placeholder": "auto-detect",
                "helper": (
                    "ID do cluster dedicado (ex: xxxx-xxxxxx-xxxxxxxx). "
                    "Vazio = auto-detect do workspace. "
                    "Necessario porque serverless nao suporta spark.hadoop.fs.s3a.*"
                ),
                "group": "advanced",
                "collapsed": True,
            },
            {
                "key": "workspace_root_bucket",
                "label": "Workspace root bucket (override)",
                "type": "text",
                "required": False,
                "placeholder": "auto: {s3_bucket}-root",
                "helper": (
                    "Bucket interno do Databricks (DBFS root, cluster logs, "
                    "init scripts). Vazio = derivado automaticamente do datalake. "
                    "So preencha pra naming convention especifica."
                ),
                "group": "advanced",
                "collapsed": True,
            },
            {
                "key": "network_cidr",
                "label": "Network CIDR (VPC)",
                "type": "text",
                "required": False,
                "placeholder": "10.0.0.0/16",
                "default": "10.0.0.0/16",
                "helper": (
                    "CIDR /16 da VPC criada pra customer-managed Databricks. "
                    "So muda se tiver overlap com outra VPC."
                ),
                "group": "advanced",
                "collapsed": True,
            },
            {
                "key": "admin_email",
                "label": "Admin email (workspace)",
                "type": "text",
                "required": False,
                "placeholder": "administrator@idlehub.com.br",
                "helper": (
                    "Email do admin adicionado ao workspace via SCIM "
                    "durante o provisioning."
                ),
                "group": "advanced",
                "collapsed": True,
            },
            {
                "key": "databricks_metastore_id",
                "label": "Metastore ID (opcional)",
                "type": "text",
                "required": False,
                "placeholder": "auto-discover",
                "helper": (
                    "Vazio = auto-discover por regiao. So preencha se a conta "
                    "tiver multiplos metastores na mesma regiao."
                ),
                "group": "advanced",
                "collapsed": True,
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
        "author": "Flowertex Labs",
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
        "author": "Flowertex Labs",
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


async def seed_demo_tenant(db: AsyncSession) -> bool:
    """Cria o tenant de demo (1 company + 1 admin + 1 pipeline). Idempotente.

    Tenant-safe: gated atras de settings.SEED_DEMO_TENANT (default False).
    Skip se a company ja existe (por slug) — nao sobrescreve dados existentes.
    Retorna True se criou algo, False se ja existia.
    """
    existing_company = await db.execute(
        select(Company).where(Company.slug == DEMO_COMPANY_SLUG)
    )
    company = existing_company.scalar_one_or_none()
    if company is None:
        company = Company(name=DEMO_COMPANY_NAME, slug=DEMO_COMPANY_SLUG)
        db.add(company)
        await db.flush()  # garante company.id para FKs abaixo

    existing_admin = await db.execute(
        select(User).where(
            User.company_id == company.id,
            User.email == DEMO_ADMIN_EMAIL,
        )
    )
    if existing_admin.scalar_one_or_none() is None:
        # role "admin" inclui permissoes chat + create_pr (ver ROLE_PERMISSIONS)
        db.add(
            User(
                company_id=company.id,
                email=DEMO_ADMIN_EMAIL,
                name=DEMO_ADMIN_NAME,
                password_hash=hash_password(DEMO_ADMIN_PASSWORD),
                role="admin",
                is_active=True,
            )
        )

    existing_pipeline = await db.execute(
        select(Pipeline).where(
            Pipeline.company_id == company.id,
            Pipeline.name == DEMO_PIPELINE_NAME,
        )
    )
    if existing_pipeline.scalar_one_or_none() is None:
        db.add(
            Pipeline(
                company_id=company.id,
                name=DEMO_PIPELINE_NAME,
                description=DEMO_PIPELINE_DESCRIPTION,
                github_repo=DEMO_PIPELINE_GITHUB_REPO,
                config={"template_slug": DEMO_PIPELINE_TEMPLATE_SLUG},
            )
        )

    await db.commit()
    logger.info("demo tenant seeded", company_slug=DEMO_COMPANY_SLUG)
    return True
