/**
 * Mock data para pipelines — usado pelo composable usePipelinesApi
 * quando mockMode esta ativo.
 */
import type { Pipeline } from "~/types/pipeline"

export const MOCK_PIPELINES: Pipeline[] = [
  {
    id: "medallion_pipeline_whatsapp",
    name: "Medallion Pipeline — WhatsApp",
    status: "SUCCESS",
    lastRunAt: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    nextRunAt: new Date(Date.now() + 1000 * 60 * 60 * 18).toISOString(),
    threadCount: 5,
  },
]
