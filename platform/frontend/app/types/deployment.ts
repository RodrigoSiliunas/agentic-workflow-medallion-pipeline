export type DeploymentStatus = "pending" | "running" | "success" | "failed" | "cancelled"
export type StepStatus = "pending" | "running" | "success" | "failed" | "skipped"
export type LogLevel = "info" | "warn" | "error" | "success" | "debug"

export interface SagaStepState {
  id: string
  name: string
  description?: string
  status: StepStatus
  startedAt?: string
  finishedAt?: string
  durationMs?: number
  errorMessage?: string
}

export interface LogEntry {
  id: string
  timestamp: string
  level: LogLevel
  message: string
  step?: string
}

export interface WorkspaceAdvancedConfig {
  rootBucket?: string
  networkCidr?: string
  adminEmail?: string
  metastoreId?: string
  /** Cluster reuse strategy: "existing" usa clusterId, "new" cria com nodeType + workers. */
  clusterMode?: "existing" | "new"
  /** Compute model: ephemeral (Job Compute, ~1/3 DBU, sem custo idle) ou persistent (all-purpose). Default ephemeral. */
  clusterCompute?: "ephemeral" | "persistent"
  /** existing mode: id do cluster ja running no workspace. */
  clusterId?: string
  /** Custom name; default = "medallion-pipeline". */
  clusterName?: string
  /** Worker node type AWS (ex m5d.large, m5d.xlarge). Default = m5d.large. */
  clusterNodeType?: string
  /** Driver node type AWS — separado pra otimizar custos. Default = mesmo do worker. */
  clusterDriverNodeType?: string
  /** Numero de workers fixos. Ignorado se autoscale set. Default = 2. */
  clusterNumWorkers?: number
  /** Autoscale min workers. Sobrepoe num_workers. */
  clusterAutoscaleMin?: number
  /** Autoscale max workers. Sobrepoe num_workers. */
  clusterAutoscaleMax?: number
  /** Auto-terminate idle minutes. Default = 30. */
  clusterAutoterminationMin?: number
  /** Versao Databricks Runtime (ex 15.4.x-scala2.12). Default = 15.4 LTS. */
  clusterSparkVersion?: string
  /** Cluster policy id (force allowlist + max workers + ttl). */
  clusterPolicyId?: string
  /** Cluster policy JSON definition — saga registra no workspace. */
  clusterPolicyDefinition?: string
  /** Custom tags propagadas pra AWS billing + Databricks usage. */
  clusterTags?: Record<string, string>
  /** Observer Agent LLM provider (anthropic/openai/google). Vazio = default empresa. */
  observerLlmProvider?: string
  /** Observer Agent model id literal (ex claude-opus-4-7). Vazio = default empresa. */
  observerLlmModel?: string
}

/** Credenciais conhecidas pre-preenchidas no wizard. Outras keys aceitas via index. */
export interface DeploymentCredentialsMap {
  aws_access_key_id: string
  aws_secret_access_key: string
  aws_region: string
  databricks_host: string
  databricks_token: string
  github_token: string
  [key: string]: string
}

export interface DeploymentConfig {
  name: string
  environment: "dev" | "staging" | "prod"
  tags: Record<string, string>
  credentials: DeploymentCredentialsMap
  envVars: Record<string, string>
  /** "existing" reusa workspace alvo (skip provisioning). "new" cria do zero. */
  workspaceMode?: "existing" | "new"
  /** workspaceMode=existing: id do workspace alvo (Databricks Account API). */
  workspaceId?: string
  /** workspaceMode=new: nome customizado do workspace (override do auto). */
  workspaceName?: string
  advanced?: WorkspaceAdvancedConfig
}

export interface Deployment {
  id: string
  templateSlug: string
  templateName: string
  config: DeploymentConfig
  status: DeploymentStatus
  createdAt: string
  startedAt?: string
  finishedAt?: string
  durationMs?: number
  steps: SagaStepState[]
  logs: LogEntry[]
  createdBy: string
  pipelineId?: string
}
