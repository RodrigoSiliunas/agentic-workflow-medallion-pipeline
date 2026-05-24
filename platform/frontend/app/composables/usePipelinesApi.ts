/**
 * API client wrapper for /api/v1/pipelines endpoints.
 * Single decision point para mock vs real — stores nunca fazem branching.
 */
import type { Pipeline, PipelineStatus } from "~/types/pipeline"
import type {
  ApproveEditResponse,
  EditorMessageResponse,
  PipelineEditSession,
  PipelineEditVersion,
  PipelineManifest,
  PipelineWorkspace,
  TransformDraft,
} from "~/types/pipeline-editor"
import { MOCK_PIPELINES } from "~/composables/mock/pipelines"

interface PipelineApiDTO {
  id: string
  name: string
  description: string | null
  databricks_job_id: number | null
  github_repo: string | null
  status?: string
  config?: Record<string, unknown> | null
}

const VALID_STATUSES: PipelineStatus[] = ["SUCCESS", "FAILED", "RUNNING", "IDLE", "RECOVERED"]

function fromApi(dto: PipelineApiDTO): Pipeline {
  const apiStatus = dto.status && VALID_STATUSES.includes(dto.status as PipelineStatus)
    ? (dto.status as PipelineStatus)
    : dto.databricks_job_id ? "SUCCESS" : "IDLE"
  return {
    id: dto.id,
    name: dto.name,
    status: apiStatus,
    lastRunAt: null,
    nextRunAt: null,
    threadCount: 0,
  }
}

function toCamelDraft(draft: Record<string, unknown>): TransformDraft {
  return {
    layer: draft.layer as TransformDraft["layer"],
    targetNode: String(draft.target_node ?? draft.targetNode ?? "silver_dedup"),
    targetTable: String(draft.target_table ?? draft.targetTable ?? ""),
    operations: ((draft.operations as Record<string, unknown>[] | undefined) || []).map((op) => ({
      op: String(op.op),
      column: op.column as string | null | undefined,
      newName: op.new_name as string | null | undefined,
      dataType: op.data_type as string | null | undefined,
      pattern: op.pattern as string | null | undefined,
      replacement: op.replacement as string | null | undefined,
      expression: op.expression as string | null | undefined,
      format: op.format as string | null | undefined,
      jsonPath: op.json_path as string | null | undefined,
      sourceColumns: (op.source_columns as string[] | undefined) || [],
      params: (op.params as Record<string, unknown> | undefined) || {},
    })),
    inputDataframe: draft.input_dataframe as string | undefined,
    outputDataframe: draft.output_dataframe as string | undefined,
    warnings: (draft.warnings as string[] | undefined) || [],
  }
}

function toApiDraft(draft: TransformDraft): Record<string, unknown> {
  return {
    layer: draft.layer,
    target_node: draft.targetNode,
    target_table: draft.targetTable,
    input_dataframe: draft.inputDataframe || "df_parsed",
    output_dataframe: draft.outputDataframe || "df_editor",
    warnings: draft.warnings || [],
    operations: draft.operations.map((op) => ({
      op: op.op,
      column: op.column,
      new_name: op.newName,
      data_type: op.dataType,
      pattern: op.pattern,
      replacement: op.replacement,
      expression: op.expression,
      format: op.format,
      json_path: op.jsonPath,
      source_columns: op.sourceColumns || [],
      params: op.params || {},
    })),
  }
}

function toWorkspace(dto: Record<string, unknown>): PipelineWorkspace {
  const manifest = dto.manifest as Record<string, unknown>
  return {
    id: String(dto.id),
    name: String(dto.name),
    description: dto.description as string | null,
    databricksJobId: dto.databricks_job_id as number | null,
    githubRepo: dto.github_repo as string | null,
    config: (dto.config as Record<string, unknown>) || {},
    manifest: {
      templateSlug: String(manifest.template_slug),
      displayName: String(manifest.display_name),
      nodes: ((manifest.nodes as Record<string, unknown>[] | undefined) || []).map((node) => ({
        id: String(node.id),
        layer: node.layer as "bronze" | "silver" | "gold",
        taskKey: String(node.task_key),
        filePath: String(node.file_path),
        inputTables: (node.input_tables as string[] | undefined) || [],
        outputTables: (node.output_tables as string[] | undefined) || [],
        supportedOperations: (node.supported_operations as string[] | undefined) || [],
        insertionMarker: String(node.insertion_marker),
      })),
    } satisfies PipelineManifest,
  }
}

function toSession(dto: Record<string, unknown>): PipelineEditSession {
  return {
    id: String(dto.id),
    pipelineId: String(dto.pipeline_id),
    title: String(dto.title),
    status: String(dto.status),
    targetLayers: (dto.target_layers as string[] | undefined) || [],
    baseRef: dto.base_ref as string | null,
    draftBranch: dto.draft_branch as string | null,
    currentVersionId: dto.current_version_id as string | null,
    createdAt: dto.created_at as string | null | undefined,
    updatedAt: dto.updated_at as string | null | undefined,
  }
}

function toVersion(dto: Record<string, unknown>): PipelineEditVersion {
  return {
    id: String(dto.id),
    sessionId: String(dto.session_id),
    versionNumber: Number(dto.version_number || 0),
    draft: toCamelDraft(dto.draft as Record<string, unknown>),
    generatedFiles: dto.generated_files as Record<string, string> | undefined,
    validationResult: dto.validation_result as Record<string, unknown> | undefined,
    previewResult: dto.preview_result as Record<string, unknown> | undefined,
    prMetadata: dto.pr_metadata as Record<string, unknown> | undefined,
    createdAt: dto.created_at as string | null | undefined,
  }
}

function toMessageResponse(dto: Record<string, unknown>): EditorMessageResponse {
  const proposal = dto.proposal as Record<string, unknown>
  return {
    sessionId: String(dto.session_id),
    message: String(dto.message),
    versionId: String(dto.version_id),
    proposal: {
      explanation: String(proposal.explanation),
      draft: toCamelDraft(proposal.draft as Record<string, unknown>),
      filesAffected: (proposal.files_affected as string[] | undefined) || [],
      riskScore: Number(proposal.risk_score || 0),
      testPlan: (proposal.test_plan as string[] | undefined) || [],
    },
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

  async function getWorkspace(id: string): Promise<PipelineWorkspace> {
    const data = await api.get<Record<string, unknown>>(`/pipelines/${id}`)
    return toWorkspace(data)
  }

  async function getStatus(id: string) {
    return api.get<Record<string, unknown>>(`/pipelines/${id}/status`)
  }

  async function listEditSessions(pipelineId: string): Promise<PipelineEditSession[]> {
    const data = await api.get<Record<string, unknown>[]>(
      `/pipelines/${pipelineId}/edit-sessions`,
    )
    return data.map(toSession)
  }

  async function createEditSession(pipelineId: string, title?: string) {
    const data = await api.post<Record<string, unknown>>(
      `/pipelines/${pipelineId}/edit-sessions`,
      { title, target_layers: ["bronze", "silver", "gold"], base_ref: "dev" },
    )
    return toSession(data)
  }

  async function sendEditMessage(pipelineId: string, sessionId: string, message: string, draft?: TransformDraft) {
    const data = await api.post<Record<string, unknown>>(
      `/pipelines/${pipelineId}/edit-sessions/${sessionId}/messages`,
      { message, draft: draft ? toApiDraft(draft) : undefined },
    )
    return toMessageResponse(data)
  }

  async function updateDraft(pipelineId: string, sessionId: string, draft: TransformDraft) {
    const data = await api.put<Record<string, unknown>>(
      `/pipelines/${pipelineId}/edit-sessions/${sessionId}/draft`,
      { draft: toApiDraft(draft) },
    )
    return toVersion(data)
  }

  async function getPreview(pipelineId: string, sessionId: string, sampleRows = 50) {
    return api.post<Record<string, unknown>>(
      `/pipelines/${pipelineId}/edit-sessions/${sessionId}/preview`,
      { sample_rows: sampleRows },
    )
  }

  async function exportPreview(pipelineId: string, sessionId: string, format: "csv" | "parquet") {
    const data = await api.post<Record<string, unknown>>(
      `/pipelines/${pipelineId}/edit-sessions/${sessionId}/export`,
      { format },
    )
    const downloadPath = String(data.download_url || "").replace(/^\/api\/v1/, "")
    if (downloadPath) {
      await api.downloadBlob(downloadPath)
    }
    return data
  }

  async function getPromptMarkdown(pipelineId: string, sessionId: string) {
    return api.get<{ filename: string; content: string }>(
      `/pipelines/${pipelineId}/edit-sessions/${sessionId}/prompt.md`,
    )
  }

  async function approveEdit(pipelineId: string, sessionId: string) {
    const data = await api.post<Record<string, unknown>>(
      `/pipelines/${pipelineId}/edit-sessions/${sessionId}/approve`,
      { create_pr: true },
    )
    return {
      status: String(data.status),
      validation: data.validation as Record<string, unknown> | undefined,
      pr: data.pr as Record<string, unknown> | undefined,
      diff: ((data.diff as Record<string, unknown>[] | undefined) || []).map((file) => ({
        path: String(file.path),
        additions: Number(file.additions || 0),
        deletions: Number(file.deletions || 0),
        patch: String(file.patch || ""),
      })),
    } satisfies ApproveEditResponse
  }

  async function getSharedPipelineEdit(token: string) {
    return api.get<Record<string, unknown>>(`/shared/pipeline-edit/${token}`)
  }

  async function revertEdit(pipelineId: string, sessionId: string, versionId?: string) {
    return api.post<Record<string, unknown>>(
      `/pipelines/${pipelineId}/edit-sessions/${sessionId}/revert`,
      { mode: "draft", version_id: versionId },
    )
  }

  async function shareArtifact(pipelineId: string, sessionId: string) {
    return api.post<Record<string, unknown>>(
      `/pipelines/${pipelineId}/edit-sessions/${sessionId}/share`,
      { role: "viewer" },
    )
  }

  return {
    list,
    getWorkspace,
    getStatus,
    listEditSessions,
    createEditSession,
    sendEditMessage,
    updateDraft,
    getPreview,
    exportPreview,
    getPromptMarkdown,
    approveEdit,
    revertEdit,
    shareArtifact,
    getSharedPipelineEdit,
  }
}
