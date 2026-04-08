export interface Pipeline {
  id: string
  name: string
  status: PipelineStatus
  lastRunAt: string | null
  nextRunAt: string | null
  threadCount: number
}

export type PipelineStatus = "SUCCESS" | "FAILED" | "RUNNING" | "IDLE" | "RECOVERED"

export interface PipelineRun {
  id: string
  status: string
  startedAt: string
  duration: number
  tasksSucceeded: number
  tasksFailed: number
}
