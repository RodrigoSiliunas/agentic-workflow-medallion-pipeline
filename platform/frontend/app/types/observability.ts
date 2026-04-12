export interface DeploymentBreakdown {
  total: number
  success: number
  failed: number
  running: number
  cancelled: number
  avgDurationSeconds: number | null
}

export interface PipelineMetrics {
  total: number
  withDatabricksJob: number
}

export interface ChannelMetrics {
  total: number
  byChannel: Record<string, number>
  connected: number
}

export interface ObserverMetrics {
  totalDiagnostics: number
  prsCreated: number
  dedupCacheHits: number
  estimatedCostUsd: number
  periodDays: number
}

export interface ObservabilityMetrics {
  companyId: string
  deployments: DeploymentBreakdown
  pipelines: PipelineMetrics
  channels: ChannelMetrics
  observer: ObserverMetrics
}
