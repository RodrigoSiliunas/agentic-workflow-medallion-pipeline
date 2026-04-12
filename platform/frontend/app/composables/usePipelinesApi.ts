/**
 * API client wrapper for /api/v1/pipelines endpoints.
 * Single decision point para mock vs real — stores nunca fazem branching.
 */
import type { Pipeline } from "~/types/pipeline"
import { MOCK_PIPELINES } from "~/composables/mock/pipelines"

interface PipelineApiDTO {
  id: string
  name: string
  description: string | null
  databricks_job_id: number | null
  github_repo: string | null
  config: Record<string, unknown> | null
}

function fromApi(dto: PipelineApiDTO): Pipeline {
  return {
    id: dto.id,
    name: dto.name,
    // Pipeline com job Databricks configurado = ativo (deployado com sucesso)
    status: dto.databricks_job_id ? "SUCCESS" : "IDLE",
    lastRunAt: null,
    nextRunAt: null,
    threadCount: 0,
  }
}

export function usePipelinesApi() {
  const api = useApiClient()
  const isMock = Boolean(useRuntimeConfig().public.mockMode)

  async function list(): Promise<Pipeline[]> {
    if (isMock) return structuredClone(MOCK_PIPELINES)
    const data = await api.get<PipelineApiDTO[]>("/pipelines")
    return data.map(fromApi)
  }

  return { list }
}
