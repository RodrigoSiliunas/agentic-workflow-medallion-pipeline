/**
 * Mock data para templates — usado pelo composable useTemplatesApi
 * quando mockMode esta ativo.
 */
import type { Template } from "~/types/template"

export const MOCK_TEMPLATES: Template[] = [
  {
    slug: "pipeline-seguradora-whatsapp",
    name: "Pipeline Seguradora WhatsApp",
    tagline: "Medallion ETL para conversas WhatsApp de seguro auto",
    description:
      "Pipeline Medallion (Bronze → Silver → Gold) sobre conversas WhatsApp de seguradora, com mascaramento PII, 12 tabelas analiticas e Observer Agent autonomo que corrige bugs via PRs no GitHub.",
    category: "ETL",
    tags: ["whatsapp", "seguros", "etl", "medallion", "pii", "observer"],
    icon: "chat-bubble-left-right",
    iconBg: "#22c55e",
    version: "1.3.0",
    author: "Safatechx Labs",
    deployCount: 47,
    durationEstimate: "8-12 min",
    architectureBullets: [
      "Bronze ingestion: S3 parquet → Delta Lake (overwrite idempotente)",
      "Silver: dedup + mascaramento PII (HMAC) + enrichment conversacional",
      "Gold: 12 tabelas analiticas (funnel, sentiment, NPS, handle_time)",
      "Validation gate: row counts, nulls, consistency",
      "Observer Agent: Claude Opus diagnostica falhas + cria PR no GitHub",
    ],
    envSchema: [
      {
        key: "catalog_name",
        label: "Unity Catalog name",
        type: "text",
        required: true,
        placeholder: "medallion",
        default: "medallion",
        helper: "Catalog principal que vai abrigar os schemas bronze/silver/gold",
      },
      {
        key: "s3_bucket",
        label: "S3 bucket name",
        type: "text",
        required: true,
        placeholder: "safatechx-medallion-datalake",
        helper: "Bucket que vai receber os parquets ingeridos",
      },
      {
        key: "schedule_cron",
        label: "Schedule (cron expression)",
        type: "cron",
        required: false,
        placeholder: "0 6 * * *",
        default: "0 6 * * *",
        helper: "Cron em timezone America/Sao_Paulo. Vazio = sem schedule",
      },
      {
        key: "masking_secret",
        label: "PII masking secret (HMAC)",
        type: "password",
        required: true,
        helper: "Chave HMAC usada para mascarar CPF, telefone, email",
      },
      {
        key: "cluster_id",
        label: "Cluster ID (opcional)",
        type: "text",
        required: false,
        placeholder: "auto-detect",
        helper:
          "ID do cluster dedicado (ex: 0409-064526-q0k9e0pd). Vazio = auto-detect do workspace. "
          + "Necessario porque serverless nao suporta spark.hadoop.fs.s3a.*",
      },
    ],
    changelog: [
      {
        version: "1.3.0",
        date: "2026-04-10",
        changes: [
          "Observer agora usa trigger automatico via task sentinel",
          "Dedup de diagnosticos via cache Delta",
          "Multi-file fixes suportados",
        ],
      },
      {
        version: "1.2.0",
        date: "2026-03-22",
        changes: [
          "Observer feedback loop via GitHub Action",
          "Validacao pre-PR com ruff + pytest",
        ],
      },
      {
        version: "1.1.0",
        date: "2026-02-15",
        changes: ["Mascaramento HMAC obrigatorio", "Schema evolution via mergeSchema"],
      },
    ],
    published: true,
  },
  {
    slug: "pipeline-crm-sap",
    name: "Pipeline CRM SAP",
    tagline: "Ingestao incremental de Accounts, Opportunities e Contacts do SAP",
    description:
      "Pipeline que conecta ao SAP via OData, faz CDC incremental das entidades de CRM (Accounts, Opportunities, Contacts, Activities), normaliza schemas e materializa views analiticas prontas para o time de vendas.",
    category: "CRM",
    tags: ["sap", "crm", "cdc", "odata", "vendas"],
    icon: "building-office-2",
    iconBg: "#3b82f6",
    version: "0.9.0",
    author: "Safatechx Labs",
    deployCount: 12,
    durationEstimate: "6-9 min",
    architectureBullets: [
      "CDC incremental via OData com high-watermark por entidade",
      "Bronze: payloads brutos particionados por data",
      "Silver: normalizacao + deduplicacao por business key",
      "Gold: Accounts 360, Funnel de Opportunities, Activity heatmap",
      "Retry com backoff exponencial em falhas do SAP",
    ],
    envSchema: [
      {
        key: "sap_host",
        label: "SAP OData endpoint",
        type: "url",
        required: true,
        placeholder: "https://sap.empresa.com.br/sap/opu/odata",
      },
      {
        key: "sap_user",
        label: "SAP username",
        type: "text",
        required: true,
      },
      {
        key: "sap_password",
        label: "SAP password",
        type: "password",
        required: true,
      },
      {
        key: "entities",
        label: "Entidades a sincronizar",
        type: "text",
        required: true,
        default: "Accounts,Opportunities,Contacts,Activities",
        helper: "Lista separada por virgula",
      },
      {
        key: "schedule_cron",
        label: "Schedule",
        type: "cron",
        required: false,
        default: "0 */4 * * *",
        helper: "Default: a cada 4 horas",
      },
    ],
    changelog: [
      {
        version: "0.9.0",
        date: "2026-04-02",
        changes: [
          "Beta publico",
          "Suporte a 4 entidades core",
          "Gold: Accounts 360 view",
        ],
      },
    ],
    published: true,
  },
  {
    slug: "pipeline-ecommerce-hotmart",
    name: "Pipeline E-commerce Hotmart",
    tagline: "Eventos de checkout, pagamento e entrega da API Hotmart",
    description:
      "Consome webhooks da Hotmart (purchase, subscription, refund) em streaming, materializa funil de conversao e cohort de recompra. Inclui alertas de anomalia em tempo real via Observer.",
    category: "E-commerce",
    tags: ["hotmart", "e-commerce", "streaming", "webhooks", "cohort"],
    icon: "shopping-cart",
    iconBg: "#ef4444",
    version: "0.6.0",
    author: "Safatechx Labs",
    deployCount: 5,
    durationEstimate: "7-10 min",
    architectureBullets: [
      "Webhook receiver → Kinesis → Delta streaming",
      "Silver: normalizacao de eventos (purchase, subscription, refund, chargeback)",
      "Gold: Funnel de checkout, Cohort de recompra, LTV por produto",
      "Observer monitora anomalia em refund_rate e dispara alerta",
    ],
    envSchema: [
      {
        key: "hotmart_client_id",
        label: "Hotmart Client ID",
        type: "text",
        required: true,
      },
      {
        key: "hotmart_client_secret",
        label: "Hotmart Client Secret",
        type: "password",
        required: true,
      },
      {
        key: "kinesis_stream",
        label: "Kinesis stream name",
        type: "text",
        required: true,
        default: "hotmart-events",
      },
      {
        key: "refund_alert_threshold",
        label: "Refund rate alert (%)",
        type: "text",
        required: false,
        default: "5",
        helper: "Dispara alerta se refund_rate > threshold em 24h",
      },
    ],
    changelog: [
      {
        version: "0.6.0",
        date: "2026-03-28",
        changes: ["Primeiro release beta", "Cohort de recompra", "LTV por produto"],
      },
    ],
    published: true,
  },
]
