/**
 * Mock data para deployments — usado pelo composable useDeploymentsApi
 * quando mockMode esta ativo.
 */
import type {
  Deployment,
  DeploymentConfig,
  DeploymentStatus,
  LogEntry,
  LogLevel,
  SagaStepState,
} from "~/types/deployment"

export const SAGA_BLUEPRINT_FALLBACK: Array<Pick<SagaStepState, "id" | "name" | "description">> = [
  { id: "validate", name: "Validate credentials", description: "AWS STS + Databricks + API keys" },
  { id: "s3", name: "Create AWS S3 bucket", description: "terraform apply 02-datalake" },
  { id: "iam", name: "Provision IAM role", description: "Role + policy Databricks" },
  { id: "secrets", name: "Create secrets scope", description: "Scope medallion-pipeline" },
  { id: "catalog", name: "Setup Unity Catalog", description: "Catalog + schemas" },
  { id: "upload", name: "Upload notebooks", description: "Sync repo Databricks" },
  { id: "observer", name: "Deploy Observer Agent", description: "Job observer_agent" },
  { id: "workflow", name: "Create workflow", description: "Job 8 tasks ETL" },
  { id: "trigger", name: "Trigger first run", description: "Run end-to-end" },
  { id: "register", name: "Register in platform", description: "Pipeline no dashboard" },
]

export const EXAMPLE_LOGS_PER_STEP: Record<string, string[]> = {
  validate: [
    "Calling AWS STS GetCallerIdentity...",
    "AWS credentials OK (account 981234567890)",
    "Validating Databricks token via w.current_user.me()...",
    "Databricks workspace reachable",
    "GitHub PAT has repo scope",
    "Anthropic API key valid (Claude Opus access)",
  ],
  s3: [
    "Initializing terraform workspace...",
    "terraform init: downloading aws provider 5.x",
    "terraform plan: + aws_s3_bucket.datalake",
    "terraform apply: creating bucket...",
    "Bucket created, enabling versioning + lifecycle rules",
  ],
  iam: [
    "Creating IAM role databricks-unity-catalog-access...",
    "Attaching policy S3ReadWrite for datalake bucket",
    "Configuring trust relationship with Databricks account",
  ],
  secrets: [
    "databricks secrets create-scope medallion-pipeline",
    "Uploading aws-access-key-id",
    "Uploading aws-secret-access-key",
    "Uploading anthropic-api-key",
    "Uploading github-token",
    "Uploading masking-secret",
  ],
  catalog: [
    "CREATE CATALOG IF NOT EXISTS medallion",
    "CREATE SCHEMA medallion.bronze",
    "CREATE SCHEMA medallion.silver",
    "CREATE SCHEMA medallion.gold",
    "CREATE SCHEMA medallion.observer",
    "Grants aplicados ao grupo de usuarios",
  ],
  upload: [
    "git clone observer-framework branch main",
    "git clone pipeline-seguradora-whatsapp",
    "POST /api/2.0/workspace/import (16 notebooks)",
    "Workspace sync completo",
  ],
  workflow: [
    "w.jobs.create(name=medallion_pipeline_whatsapp)",
    "Task 1/8: pre_check",
    "Task 2/8: bronze_ingestion",
    "Tasks 3-5/8: silver_* (dedup, entities, enrichment)",
    "Task 6/8: gold_analytics (12 subnotebooks)",
    "Task 7/8: validation",
    "Task 8/8: observer_trigger (run_if AT_LEAST_ONE_FAILED)",
    "Schedule registrado: cron 0 6 * * *",
  ],
  observer: [
    "Creating workflow observer_agent...",
    "Task 1/1: collect_and_fix (notebook do observer-framework)",
    "Observer pronto para diagnostico automatico",
  ],
  trigger: [
    "w.jobs.run_now(job_id=777105089901314)",
    "Run ID 826862455884866 iniciado",
    "Aguardando conclusao...",
    "bronze_ingestion: SUCCESS (125.9s, 153228 rows)",
    "silver_*: SUCCESS",
    "gold_analytics: SUCCESS (12 tabelas)",
    "validation: SUCCESS (all gates passed)",
    "observer_trigger: EXCLUDED (no failures)",
    "Run completo",
  ],
  register: [
    "Adicionando pipeline ao dashboard Flowertex",
    "Configurando chat agent para este workflow",
    "Deployment finalizado com sucesso",
  ],
}

function generateMockDeployment(
  slug: string,
  name: string,
  status: DeploymentStatus,
  daysAgo: number,
  failAt?: string,
): Deployment {
  const now = Date.now()
  const createdAt = new Date(now - daysAgo * 24 * 60 * 60 * 1000).toISOString()
  const steps: SagaStepState[] = SAGA_BLUEPRINT_FALLBACK.map((b) => ({
    ...b,
    status: "pending",
  }))

  if (status === "success" || status === "failed") {
    let idx = 0
    for (const step of steps) {
      if (status === "failed" && step.id === failAt) {
        step.status = "failed"
        step.errorMessage = "Terraform apply failed: access denied to IAM role creation"
        break
      }
      step.status = "success"
      step.durationMs = 2000 + Math.floor(Math.random() * 3000)
      step.finishedAt = new Date(new Date(createdAt).getTime() + step.durationMs * (idx + 1)).toISOString()
      idx++
    }
  }

  const logs: LogEntry[] = []
  let logIdx = 0
  for (const step of steps) {
    if (step.status === "pending") break
    const messages = EXAMPLE_LOGS_PER_STEP[step.id] ?? []
    for (const msg of messages) {
      logs.push({
        id: `log-${logIdx++}`,
        timestamp: new Date(new Date(createdAt).getTime() + logIdx * 500).toISOString(),
        level: "info",
        message: msg,
        step: step.id,
      })
    }
    if (step.status === "failed") {
      logs.push({
        id: `log-${logIdx++}`,
        timestamp: new Date(new Date(createdAt).getTime() + logIdx * 500).toISOString(),
        level: "error",
        message: step.errorMessage ?? "Step failed",
        step: step.id,
      })
    }
  }

  const duration = steps.reduce((sum, s) => sum + (s.durationMs ?? 0), 0)
  const finishedAt =
    status === "success" || status === "failed"
      ? new Date(new Date(createdAt).getTime() + duration).toISOString()
      : undefined

  return {
    id: `dep-${Math.random().toString(36).slice(2, 10)}`,
    templateSlug: slug,
    templateName: name,
    config: {
      name: `${name} — prod`,
      environment: "prod",
      tags: { company: "flowertex", team: "data-platform" },
      credentials: {
        aws_access_key_id: "",
        aws_secret_access_key: "",
        aws_region: "",
        databricks_host: "",
        databricks_token: "",
        github_token: "",
      },
      envVars: {},
    },
    status,
    createdAt,
    startedAt: createdAt,
    finishedAt,
    durationMs: duration || undefined,
    steps,
    logs,
    createdBy: "Rodrigo Siliunas",
  }
}

export const MOCK_DEPLOYMENTS: Deployment[] = [
  generateMockDeployment("pipeline-seguradora-whatsapp", "Pipeline Seguradora WhatsApp", "success", 2),
  generateMockDeployment("pipeline-crm-sap", "Pipeline CRM SAP", "failed", 5, "iam"),
  generateMockDeployment("pipeline-ecommerce-hotmart", "Pipeline E-commerce Hotmart", "success", 12),
]

export function emitLog(deployment: Deployment, level: LogLevel, message: string, step?: string) {
  deployment.logs.push({
    id: `log-${deployment.logs.length}`,
    timestamp: new Date().toISOString(),
    level,
    message,
    step,
  })
}

export function createDeploymentLocalMock(
  templateSlug: string,
  templateName: string,
  cfg: DeploymentConfig,
): Deployment {
  const id = `dep-${Math.random().toString(36).slice(2, 10)}`
  return {
    id,
    templateSlug,
    templateName,
    config: cfg,
    status: "pending",
    createdAt: new Date().toISOString(),
    steps: SAGA_BLUEPRINT_FALLBACK.map((b) => ({ ...b, status: "pending" })),
    logs: [],
    createdBy: "Rodrigo Siliunas",
  }
}

export async function runSagaMock(deployment: Deployment): Promise<void> {
  deployment.status = "running"
  deployment.startedAt = new Date().toISOString()
  emitLog(deployment, "info", `Starting deployment of ${deployment.templateName}...`)

  const totalStart = Date.now()

  for (const step of deployment.steps) {
    step.status = "running"
    step.startedAt = new Date().toISOString()
    emitLog(deployment, "info", `→ ${step.name}`, step.id)

    const messages = EXAMPLE_LOGS_PER_STEP[step.id] ?? []
    for (const msg of messages) {
      await new Promise((r) => setTimeout(r, 250 + Math.random() * 250))
      emitLog(deployment, "info", msg, step.id)
    }

    const stepDuration = Date.now() - new Date(step.startedAt).getTime()
    step.durationMs = stepDuration
    step.finishedAt = new Date().toISOString()
    step.status = "success"
    emitLog(deployment, "success", `${step.name} completed in ${stepDuration}ms`, step.id)
  }

  deployment.status = "success"
  deployment.finishedAt = new Date().toISOString()
  deployment.durationMs = Date.now() - totalStart
  emitLog(
    deployment,
    "success",
    `Deployment successful in ${Math.round(deployment.durationMs / 1000)}s`,
  )

  deployment.pipelineId = deployment.templateSlug
}
