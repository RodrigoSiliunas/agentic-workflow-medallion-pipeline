export type PipelineLayer = "bronze" | "silver" | "gold"

export interface TransformOperation {
  op: string
  column?: string | null
  newName?: string | null
  dataType?: string | null
  pattern?: string | null
  replacement?: string | null
  expression?: string | null
  format?: string | null
  jsonPath?: string | null
  sourceColumns?: string[]
  params?: Record<string, unknown>
}

export interface TransformDraft {
  layer: PipelineLayer
  targetNode: string
  targetTable: string
  operations: TransformOperation[]
  inputDataframe?: string
  outputDataframe?: string
  warnings?: string[]
}

export interface EditProposal {
  explanation: string
  draft: TransformDraft
  filesAffected: string[]
  riskScore: number
  testPlan: string[]
}

export interface PipelineManifestNode {
  id: string
  layer: PipelineLayer
  taskKey: string
  filePath: string
  inputTables: string[]
  outputTables: string[]
  supportedOperations: string[]
  insertionMarker: string
}

export interface PipelineManifest {
  templateSlug: string
  displayName: string
  nodes: PipelineManifestNode[]
}

export interface PipelineWorkspace {
  id: string
  name: string
  description: string | null
  databricksJobId: number | null
  githubRepo: string | null
  config: Record<string, unknown>
  manifest: PipelineManifest
}

export interface PipelineEditSession {
  id: string
  pipelineId: string
  title: string
  status: string
  targetLayers: string[]
  baseRef: string | null
  draftBranch: string | null
  currentVersionId: string | null
  createdAt?: string | null
  updatedAt?: string | null
  // PR aberto pela sessao (preenchido apos approve com create_pr)
  prNumber?: number | null
  prUrl?: string | null
}

export interface PipelineEditVersion {
  id: string
  sessionId: string
  versionNumber: number
  draft: TransformDraft
  generatedFiles?: Record<string, string>
  validationResult?: Record<string, unknown>
  previewResult?: Record<string, unknown>
  prMetadata?: Record<string, unknown>
  createdAt?: string | null
}

export interface EditorMessageResponse {
  sessionId: string
  message: string
  proposal: EditProposal
  versionId: string
}

export interface CodeDiffFile {
  path: string
  additions: number
  deletions: number
  patch: string
}

export interface ApproveEditResponse {
  status: string
  validation?: Record<string, unknown>
  pr?: Record<string, unknown>
  diff?: CodeDiffFile[]
}
