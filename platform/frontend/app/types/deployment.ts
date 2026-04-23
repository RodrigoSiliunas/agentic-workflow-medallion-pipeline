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
