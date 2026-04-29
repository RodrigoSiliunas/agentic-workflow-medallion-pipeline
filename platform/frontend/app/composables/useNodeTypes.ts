/**
 * Composable Databricks node types — alimenta filtro do ClusterPicker.
 *
 * Workspace tier + region restringe quais node types Databricks aceita
 * (ex: Premium nao tem t-series). Filtra catalogo curado pra so mostrar
 * tipos validos no workspace alvo, evitando "node type not supported"
 * tardio na saga.
 */

export interface DatabricksNodeType {
  node_type_id: string
  memory_mb: number | null
  num_cores: number | null
  category: string | null
}

export function useNodeTypes() {
  const api = useApiClient()
  const allowedIds = ref<Set<string>>(new Set())
  const workspaceConfigured = ref<boolean | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function load() {
    loading.value = true
    error.value = null
    try {
      const resp = await api.get<{
        workspace_configured: boolean
        node_types: DatabricksNodeType[]
      }>("/databricks/node-types")
      workspaceConfigured.value = resp.workspace_configured
      allowedIds.value = new Set(
        (resp.node_types || []).map((n) => n.node_type_id).filter(Boolean),
      )
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      allowedIds.value = new Set()
      workspaceConfigured.value = null
    } finally {
      loading.value = false
    }
  }

  /** True se id e suportado OU se ainda nao carregamos a lista (sem filtrar). */
  function isAllowed(id: string): boolean {
    if (allowedIds.value.size === 0) return true
    return allowedIds.value.has(id)
  }

  return {
    allowedIds,
    workspaceConfigured,
    loading,
    error,
    load,
    isAllowed,
  }
}
