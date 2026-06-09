/**
 * Mock data para o Pipeline Editor V2 — portado de fbaf2c9a-*.js.
 * Chaves em camelCase para casar com a saída de usePipelinesApi.
 * Preview usa snake_case (cru do backend) — mapeado em usePipelineEditorSession.
 */
import type {
  PipelineEditSession,
  PipelineWorkspace,
  EditorMessageResponse,
  ValidationResult,
  FileDiff,
  SchemaColumn,
} from "~/types/pipeline-editor-v2"

export const MOCK_WORKSPACE: PipelineWorkspace = {
  id: "medallion_pipeline_whatsapp",
  name: "Medallion Pipeline — WhatsApp",
  description: "Pipeline de conversas WhatsApp de seguro auto (~153k mensagens)",
  databricksJobId: 777105089901314,
  githubRepo: "RodrigoSiliunas/agentic-workflow-medallion-pipeline",
  config: {},
  manifest: {
    templateSlug: "pipeline-seguradora-whatsapp",
    displayName: "Seguradora WhatsApp",
    nodes: [
      {
        id: "silver_messages",
        layer: "silver",
        taskKey: "silver_messages",
        filePath: "pipelines/pipeline-seguradora-whatsapp/notebooks/silver/dedup_clean.py",
        inputTables: ["bronze.messages"],
        outputTables: ["silver.messages"],
        supportedOperations: [
          "rename_column", "drop_column", "cast_column", "trim",
          "regex_replace", "derive_column", "filter_rows", "mask_pii",
        ],
        insertionMarker: "# EDITOR_INSERTION_POINT",
      },
    ],
  },
}

export const MOCK_SESSIONS: PipelineEditSession[] = [
  {
    id: "ses_a4f2",
    pipelineId: "medallion_pipeline_whatsapp",
    title: "Renomear cliente_id → customer_id",
    status: "preview_ok",
    targetLayers: ["silver"],
    baseRef: "dev",
    draftBranch: "pipeline-editor/ses_a4f2",
    currentVersionId: "ver_001",
    createdAt: "2026-06-05T14:18:00Z",
    updatedAt: "2026-06-05T14:30:00Z",
  },
  {
    id: "ses_38be",
    pipelineId: "medallion_pipeline_whatsapp",
    title: "Mascarar PII em silver_users",
    status: "pr_created",
    targetLayers: ["silver"],
    baseRef: "dev",
    draftBranch: "pipeline-editor/ses_38be",
    currentVersionId: "ver_002",
    createdAt: "2026-06-04T12:00:00Z",
    updatedAt: "2026-06-05T10:00:00Z",
  },
  {
    id: "ses_71cd",
    pipelineId: "medallion_pipeline_whatsapp",
    title: "Derivar full_name a partir de first/last",
    status: "validated",
    targetLayers: ["silver"],
    baseRef: "dev",
    draftBranch: null,
    currentVersionId: "ver_003",
    createdAt: "2026-06-03T10:00:00Z",
    updatedAt: "2026-06-04T08:00:00Z",
  },
  {
    id: "ses_92ee",
    pipelineId: "medallion_pipeline_whatsapp",
    title: "Filtrar mensagens canceladas",
    status: "draft",
    targetLayers: ["silver"],
    baseRef: "dev",
    draftBranch: null,
    currentVersionId: null,
    createdAt: "2026-06-04T16:00:00Z",
    updatedAt: "2026-06-04T16:00:00Z",
  },
  {
    id: "ses_5519",
    pipelineId: "medallion_pipeline_whatsapp",
    title: "Cast amount para decimal(18,2)",
    status: "validation_failed",
    targetLayers: ["silver"],
    baseRef: "dev",
    draftBranch: null,
    currentVersionId: "ver_004",
    createdAt: "2026-06-02T09:00:00Z",
    updatedAt: "2026-06-02T09:30:00Z",
  },
]

export const MOCK_PROPOSAL_J1_RESPONSE: EditorMessageResponse = {
  sessionId: "ses_a4f2",
  versionId: "ver_001",
  message:
    "Vou montar a proposta — três operações na camada Silver. Avalia se bate antes de eu rodar o preview.",
  proposal: {
    explanation:
      "Para padronizar com o esquema de exportação, vou renomear `cliente_id` para `customer_id` na tabela `silver.messages` e remover a coluna `ssn` (PII desnecessária no Silver). Também aplico `trim` em `nome_completo` para normalizar.",
    draft: {
      layer: "silver",
      targetNode: "silver_messages",
      targetTable: "silver.messages",
      operations: [
        { op: "rename_column", column: "cliente_id", newName: "customer_id" },
        { op: "drop_column", column: "ssn" },
        { op: "trim", column: "nome_completo" },
      ],
    },
    filesAffected: [
      "pipelines/seguradora_whatsapp/silver/messages.py",
      "pipelines/seguradora_whatsapp/silver/_schema.yaml",
      "pipelines/seguradora_whatsapp/tests/test_silver_messages.py",
    ],
    riskScore: 2.4,
    testPlan: [
      "Confirmar que `customer_id` existe e tem 0 nulls no preview after",
      "Verificar que `ssn` não aparece no schema after",
      "Re-rodar testes unitários do silver_messages",
    ],
  },
}

// Preview cru do backend (snake_case) — mapeado em usePipelineEditorSession.runPreview()
export const MOCK_PREVIEW_OK_RAW: Record<string, unknown> = {
  status: "ready",
  namespace: "preview_co_b8a1_pip_3e21_ses_a4f2",
  duration: "27.4s",
  schema_delta: {
    // Backend serializa `dropped`; o mapper (mapSchemaDelta) converte para `removed`.
    dropped: ["ssn"],
    renamed: [{ from: "cliente_id", to: "customer_id" }],
    derived: [],
  },
  schema_before: [
    { name: "cliente_id", type: "string", nullable: false, comment: "Identificador legado" },
    { name: "nome_completo", type: "string", nullable: true },
    { name: "ssn", type: "string", nullable: true, comment: "PII · CPF mascarado" },
    { name: "status", type: "string", nullable: false },
    { name: "channel", type: "string", nullable: false, comment: "whatsapp | telegram" },
    { name: "amount", type: "decimal(18,2)", nullable: true },
    { name: "created_at", type: "timestamp", nullable: false },
    { name: "updated_at", type: "timestamp", nullable: true },
  ] as SchemaColumn[],
  schema_after: [
    { name: "customer_id", type: "string", nullable: false, state: "renamed", from: "cliente_id", comment: "Identificador legado" },
    { name: "nome_completo", type: "string", nullable: true, state: "modified", note: "trim aplicado" },
    { name: "status", type: "string", nullable: false, state: "unchanged" },
    { name: "channel", type: "string", nullable: false, state: "unchanged", comment: "whatsapp | telegram" },
    { name: "amount", type: "decimal(18,2)", nullable: true, state: "unchanged" },
    { name: "created_at", type: "timestamp", nullable: false, state: "unchanged" },
    { name: "updated_at", type: "timestamp", nullable: true, state: "unchanged" },
  ] as SchemaColumn[],
  rows_before: [
    { cliente_id: "C-1042", nome_completo: " Maria Silva ", ssn: "***-12-3456", status: "active", created_at: "2026-04-12" },
    { cliente_id: "C-1043", nome_completo: "João Pereira", ssn: "***-44-1109", status: "cancelled", created_at: "2026-04-13" },
    { cliente_id: "C-1044", nome_completo: " Ana Costa", ssn: "***-89-7732", status: "active", created_at: "2026-04-13" },
    { cliente_id: "C-1045", nome_completo: "Pedro Lima ", ssn: "***-22-3401", status: "active", created_at: "2026-04-14" },
    { cliente_id: "C-1046", nome_completo: "Carla Mendes", ssn: "***-67-9982", status: "cancelled", created_at: "2026-04-14" },
  ],
  rows_after: [
    { customer_id: "C-1042", nome_completo: "Maria Silva", status: "active", created_at: "2026-04-12" },
    { customer_id: "C-1043", nome_completo: "João Pereira", status: "cancelled", created_at: "2026-04-13" },
    { customer_id: "C-1044", nome_completo: "Ana Costa", status: "active", created_at: "2026-04-13" },
    { customer_id: "C-1045", nome_completo: "Pedro Lima", status: "active", created_at: "2026-04-14" },
    { customer_id: "C-1046", nome_completo: "Carla Mendes", status: "cancelled", created_at: "2026-04-14" },
  ],
}

export const MOCK_VALIDATION_OK: ValidationResult = {
  valid: true,
  checks: [
    { label: "Codegen PySpark", state: "ok" },
    { label: "Ruff lint", state: "ok" },
    { label: "Schema compatível", state: "ok" },
    { label: "Marker injetado", state: "ok" },
  ],
}

export const MOCK_FILE_DIFFS: FileDiff[] = [
  {
    path: "pipelines/seguradora_whatsapp/silver/messages.py",
    additions: 12,
    deletions: 4,
    patch: "@@ -14,8 +14,16 @@ def transform_silver_messages\n+    df = (\n+        df\n+        .withColumnRenamed('cliente_id', 'customer_id')\n-    df = df.select('cliente_id')",
  },
  {
    path: "pipelines/seguradora_whatsapp/silver/_schema.yaml",
    additions: 8,
    deletions: 2,
    patch: "@@ -3,12 +3,18 @@ table: silver.messages\n+  - name: customer_id\n-  - name: cliente_id",
  },
  {
    path: "pipelines/seguradora_whatsapp/tests/test_silver_messages.py",
    additions: 18,
    deletions: 6,
    patch: "@@ -22,9 +22,21 @@ def test_silver_messages_schema\n+    assert 'customer_id' in df.columns\n-    assert 'cliente_id' in df.columns",
  },
]

export const MOCK_TARGET_TABLE_COLUMNS: SchemaColumn[] = [
  { name: "cliente_id", type: "string", nullable: false, comment: "Identificador legado" },
  { name: "nome_completo", type: "string", nullable: true },
  { name: "ssn", type: "string", nullable: true, comment: "CPF mascarado", pii: true },
  { name: "cpf", type: "string", nullable: true, comment: "CPF cliente", pii: true },
  { name: "email", type: "string", nullable: true, pii: true },
  { name: "status", type: "string", nullable: false },
  { name: "channel", type: "string", nullable: false, comment: "whatsapp | telegram" },
  { name: "amount", type: "decimal(18,2)", nullable: true },
  { name: "created_at", type: "timestamp", nullable: false },
  { name: "updated_at", type: "timestamp", nullable: true },
  { name: "payload", type: "string", nullable: true, comment: "JSON cru do webhook" },
]
