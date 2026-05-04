/**
 * API client wrapper for /api/v1/deployments endpoints + SSE subscriber.
 * Single decision point para mock vs real — stores nunca fazem branching.
 */
import type { Deployment, DeploymentConfig, LogEntry, SagaStepState } from "~/types/deployment"
import {
  MOCK_DEPLOYMENTS,
  SAGA_BLUEPRINT_FALLBACK,
  createDeploymentLocalMock,
} from "~/composables/mock/deployments"

interface DeploymentStepDTO {
  id: string
  step_id: string
  name: string
  description: string | null
  status: string
  order_index: number
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  error_message: string | null
}

interface DeploymentLogDTO {
  id: string
  level: string
  message: string
  step_id: string | null
  created_at: string
}

interface DeploymentApiDTO {
  id: string
  template_slug: string
  template_name: string
  name: string
  environment: string
  config: Record<string, unknown>
  status: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  pipeline_id: string | null
  steps: DeploymentStepDTO[]
  logs: DeploymentLogDTO[]
}

interface DeploymentListItemDTO {
  id: string
  template_slug: string
  template_name: string
  name: string
  environment: string
  status: string
  created_at: string
  finished_at: string | null
  duration_ms: number | null
}

function stepFromApi(dto: DeploymentStepDTO): SagaStepState {
  return {
    id: dto.step_id,
    name: dto.name,
    description: dto.description ?? undefined,
    status: dto.status as SagaStepState["status"],
    startedAt: dto.started_at ?? undefined,
    finishedAt: dto.finished_at ?? undefined,
    durationMs: dto.duration_ms ?? undefined,
    errorMessage: dto.error_message ?? undefined,
  }
}

function logFromApi(dto: DeploymentLogDTO): LogEntry {
  return {
    id: dto.id,
    timestamp: dto.created_at,
    level: dto.level as LogEntry["level"],
    message: dto.message,
    step: dto.step_id ?? undefined,
  }
}

function deploymentFromApi(dto: DeploymentApiDTO): Deployment {
  return {
    id: dto.id,
    templateSlug: dto.template_slug,
    templateName: dto.template_name,
    config: {
      name: dto.name,
      environment: dto.environment as DeploymentConfig["environment"],
      tags: (dto.config?.tags as Record<string, string>) ?? {},
      credentials: (dto.config?.credentials as DeploymentConfig["credentials"]) ?? (
        {} as DeploymentConfig["credentials"]
      ),
      envVars: (dto.config?.env_vars as Record<string, string>) ?? {},
    },
    status: dto.status as Deployment["status"],
    createdAt: dto.created_at,
    startedAt: dto.started_at ?? undefined,
    finishedAt: dto.finished_at ?? undefined,
    durationMs: dto.duration_ms ?? undefined,
    steps: dto.steps.map(stepFromApi),
    logs: dto.logs.map(logFromApi),
    createdBy: "",
    pipelineId: dto.pipeline_id ?? undefined,
  }
}

function summaryFromApi(dto: DeploymentListItemDTO): Deployment {
  return {
    id: dto.id,
    templateSlug: dto.template_slug,
    templateName: dto.template_name,
    config: {
      name: dto.name,
      environment: dto.environment as DeploymentConfig["environment"],
      tags: {},
      credentials: {} as DeploymentConfig["credentials"],
      envVars: {},
    },
    status: dto.status as Deployment["status"],
    createdAt: dto.created_at,
    finishedAt: dto.finished_at ?? undefined,
    durationMs: dto.duration_ms ?? undefined,
    steps: [],
    logs: [],
    createdBy: "",
  }
}

export interface DeploymentEvent {
  type: "connected" | "step_update" | "log" | "status_change" | "complete" | "error"
  deployment_id: string
  data?: Record<string, unknown>
}

export function useDeploymentsApi() {
  const api = useApiClient()
  const auth = useAuthStore()
  const isMock = Boolean(useRuntimeConfig().public.mockMode)

  async function getBlueprint(): Promise<Array<{ id: string; name: string; description: string }>> {
    if (isMock) return structuredClone(SAGA_BLUEPRINT_FALLBACK)
    return api.get("/deployments/blueprint")
  }

  async function list(): Promise<Deployment[]> {
    if (isMock) return structuredClone(MOCK_DEPLOYMENTS)
    const data = await api.get<DeploymentListItemDTO[]>("/deployments")
    return data.map(summaryFromApi)
  }

  async function getById(id: string): Promise<Deployment | null> {
    if (isMock) return null
    try {
      const data = await api.get<DeploymentApiDTO>(`/deployments/${id}`)
      return deploymentFromApi(data)
    } catch {
      return null
    }
  }

  async function create(templateSlug: string, config: DeploymentConfig): Promise<Deployment> {
    if (isMock) {
      return createDeploymentLocalMock(templateSlug, `Template ${templateSlug}`, config)
    }
    const advancedPayload = config.advanced
      ? {
          root_bucket: config.advanced.rootBucket,
          network_cidr: config.advanced.networkCidr,
          admin_email: config.advanced.adminEmail,
          metastore_id: config.advanced.metastoreId,
          cluster_compute: config.advanced.clusterCompute,
          cluster_name: config.advanced.clusterName,
          cluster_node_type: config.advanced.clusterNodeType,
          cluster_driver_node_type: config.advanced.clusterDriverNodeType,
          cluster_num_workers: config.advanced.clusterNumWorkers,
          cluster_autoscale_min: config.advanced.clusterAutoscaleMin,
          cluster_autoscale_max: config.advanced.clusterAutoscaleMax,
          cluster_autotermination_min: config.advanced.clusterAutoterminationMin,
          cluster_spark_version: config.advanced.clusterSparkVersion,
          cluster_policy_id: config.advanced.clusterPolicyId,
          cluster_policy_definition: config.advanced.clusterPolicyDefinition,
          cluster_tags: config.advanced.clusterTags,
          observer_llm_provider: config.advanced.observerLlmProvider,
          observer_llm_model: config.advanced.observerLlmModel,
        }
      : undefined
    const data = await api.post<DeploymentApiDTO>("/deployments", {
      template_slug: templateSlug,
      config: {
        name: config.name,
        environment: config.environment,
        tags: config.tags,
        credentials: config.credentials,
        env_vars: config.envVars,
        workspace_mode: config.workspaceMode ?? "new",
        workspace_id: config.workspaceId,
        workspace_name: config.workspaceName,
        advanced: advancedPayload,
      },
    })
    return deploymentFromApi(data)
  }

  async function cancel(id: string): Promise<void> {
    if (isMock) return
    await api.post(`/deployments/${id}/cancel`, {})
  }

  async function remove(id: string): Promise<void> {
    if (isMock) return
    await api.delete(`/deployments/${id}`)
  }

  function subscribeEvents(
    id: string,
    handlers: {
      onStep?: (stepId: string, status: string, durationMs?: number) => void
      onLog?: (log: LogEntry) => void
      onStatusChange?: (status: string) => void
      onComplete?: () => void
      onError?: (message: string) => void
    },
  ): () => void {
    if (!import.meta.client) return () => {}
    const url = `${api.baseURL}/deployments/${id}/events`
    // native EventSource nao suporta Authorization headers; usamos fetch + ReadableStream.
    const controller = new AbortController()

    void (async () => {
      try {
        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${auth.accessToken}`,
            Accept: "text/event-stream",
          },
          signal: controller.signal,
          credentials: "include",
        })
        if (!response.ok || !response.body) {
          handlers.onError?.(`SSE stream failed: ${response.status}`)
          return
        }
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() ?? ""
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            try {
              const event = JSON.parse(line.slice(6)) as DeploymentEvent
              dispatchEvent(event, handlers)
            } catch {
              // malformed — skip
            }
          }
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          handlers.onError?.(e instanceof Error ? e.message : "SSE error")
        }
      }
    })()

    return () => controller.abort()
  }

  function dispatchEvent(
    event: DeploymentEvent,
    handlers: Parameters<typeof subscribeEvents>[1],
  ) {
    switch (event.type) {
      case "step_update":
        handlers.onStep?.(
          String(event.data?.step_id ?? ""),
          String(event.data?.status ?? ""),
          event.data?.duration_ms as number | undefined,
        )
        break
      case "log":
        handlers.onLog?.({
          id: String(event.data?.id ?? crypto.randomUUID()),
          timestamp: String(event.data?.timestamp ?? new Date().toISOString()),
          level: (event.data?.level as LogEntry["level"]) ?? "info",
          message: String(event.data?.message ?? ""),
          step: event.data?.step_id as string | undefined,
        })
        break
      case "status_change":
        handlers.onStatusChange?.(String(event.data?.status ?? ""))
        break
      case "complete":
        handlers.onComplete?.()
        break
      case "error":
        handlers.onError?.(String(event.data?.message ?? "Unknown error"))
        break
    }
  }

  return { getBlueprint, list, getById, create, cancel, remove, subscribeEvents }
}
