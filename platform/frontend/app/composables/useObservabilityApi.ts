/**
 * API wrapper para /api/v1/observability.
 */
import type { ObservabilityMetrics } from "~/types/observability"

interface MetricsDTO {
  company_id: string
  deployments: {
    total: number
    success: number
    failed: number
    running: number
    cancelled: number
    avg_duration_seconds: number | null
  }
  pipelines: {
    total: number
    with_databricks_job: number
  }
  channels: {
    total: number
    by_channel: Record<string, number>
    connected: number
  }
  observer: {
    total_diagnostics: number
    prs_created: number
    dedup_cache_hits: number
    estimated_cost_usd: number
    period_days: number
  }
}

const MOCK: ObservabilityMetrics = {
  companyId: "mock",
  deployments: {
    total: 3,
    success: 2,
    failed: 1,
    running: 0,
    cancelled: 0,
    avgDurationSeconds: 22.4,
  },
  pipelines: { total: 1, withDatabricksJob: 1 },
  channels: {
    total: 3,
    byChannel: { whatsapp: 1, discord: 1, telegram: 1 },
    connected: 2,
  },
  observer: {
    totalDiagnostics: 23,
    prsCreated: 19,
    dedupCacheHits: 18,
    estimatedCostUsd: 4.82,
    periodDays: 30,
  },
}

export function useObservabilityApi() {
  const api = useApiClient()
  const config = useRuntimeConfig()

  async function getMetrics(): Promise<ObservabilityMetrics> {
    if (config.public.mockMode) return structuredClone(MOCK)
    try {
      const dto = await api.get<MetricsDTO>("/observability/metrics")
      return {
        companyId: dto.company_id,
        deployments: {
          total: dto.deployments.total,
          success: dto.deployments.success,
          failed: dto.deployments.failed,
          running: dto.deployments.running,
          cancelled: dto.deployments.cancelled,
          avgDurationSeconds: dto.deployments.avg_duration_seconds,
        },
        pipelines: {
          total: dto.pipelines.total,
          withDatabricksJob: dto.pipelines.with_databricks_job,
        },
        channels: {
          total: dto.channels.total,
          byChannel: dto.channels.by_channel,
          connected: dto.channels.connected,
        },
        observer: {
          totalDiagnostics: dto.observer.total_diagnostics,
          prsCreated: dto.observer.prs_created,
          dedupCacheHits: dto.observer.dedup_cache_hits,
          estimatedCostUsd: dto.observer.estimated_cost_usd,
          periodDays: dto.observer.period_days,
        },
      }
    } catch {
      return structuredClone(MOCK)
    }
  }

  return { getMetrics }
}
