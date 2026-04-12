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

export interface DeploymentConfig {
  name: string
  environment: "dev" | "staging" | "prod"
  tags: Record<string, string>
  credentials: Record<string, string>
  envVars: Record<string, string>
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
