/**
 * Composable Databricks Account introspection — alimenta o WorkspacePicker
 * do wizard de deploy.
 *
 * Consume os endpoints `/api/v1/databricks/*` (ver `routes/databricks.py`).
 * Caching local na vida do componente: lista carregada uma vez, config
 * carregada on-demand quando user seleciona um workspace.
 */

export interface DatabricksWorkspaceSummary {
  workspace_id: number
  workspace_name: string
  deployment_name: string | null
  workspace_status: string | null
  aws_region: string | null
  has_network: boolean
  has_storage_config: boolean
}

export interface DatabricksWorkspaceConfig {
  workspace_id: number
  workspace_name: string
  deployment_name: string | null
  workspace_status: string | null
  aws_region: string | null
  network_id: string | null
  credentials_id: string | null
  storage_configuration_id: string | null
  root_bucket_name: string | null
  metastore_id: string | null
  metastore_attached: boolean
}

export interface DatabricksMetastore {
  metastore_id: string
  name: string
  region: string
  default_data_access_config_id: string | null
}

export function useDatabricksWorkspaces() {
  const api = useApiClient()
  const workspaces = ref<DatabricksWorkspaceSummary[]>([])
  const oauthConfigured = ref<boolean | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadWorkspaces() {
    loading.value = true
    error.value = null
    try {
      const resp = await api.get<{
        oauth_configured: boolean
        workspaces: DatabricksWorkspaceSummary[]
      }>("/api/v1/databricks/workspaces")
      oauthConfigured.value = resp.oauth_configured
      workspaces.value = resp.workspaces || []
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      workspaces.value = []
      oauthConfigured.value = null
    } finally {
      loading.value = false
    }
  }

  async function fetchWorkspaceConfig(
    workspaceId: number,
  ): Promise<DatabricksWorkspaceConfig> {
    return api.get<DatabricksWorkspaceConfig>(
      `/api/v1/databricks/workspaces/${workspaceId}/config`,
    )
  }

  async function listMetastores(region?: string): Promise<DatabricksMetastore[]> {
    const params = region ? { region } : undefined
    const resp = await api.get<{
      oauth_configured: boolean
      metastores: DatabricksMetastore[]
    }>("/api/v1/databricks/metastores", params)
    return resp.metastores || []
  }

  return {
    workspaces,
    oauthConfigured,
    loading,
    error,
    loadWorkspaces,
    fetchWorkspaceConfig,
    listMetastores,
  }
}
