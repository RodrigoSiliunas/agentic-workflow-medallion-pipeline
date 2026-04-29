/**
 * Composable Databricks cluster policies — alimenta dropdown do wizard advanced.
 *
 * Fetcha lista do workspace alvo via backend (/api/v1/databricks/policies).
 * Usuario pode selecionar policy pra forcar guardrails (allowlist node types,
 * max workers, mandatory autotermination). Vazio = sem policy.
 */

export interface ClusterPolicy {
  policy_id: string
  name: string
  description: string | null
  /** JSON raw da policy definition (Databricks format) — opcional uso */
  definition: string | null
}

export function useClusterPolicies() {
  const api = useApiClient()
  const policies = ref<ClusterPolicy[]>([])
  const workspaceConfigured = ref<boolean | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function load() {
    loading.value = true
    error.value = null
    try {
      const resp = await api.get<{
        workspace_configured: boolean
        policies: ClusterPolicy[]
      }>("/databricks/policies")
      workspaceConfigured.value = resp.workspace_configured
      policies.value = resp.policies || []
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      policies.value = []
      workspaceConfigured.value = null
    } finally {
      loading.value = false
    }
  }

  return {
    policies,
    workspaceConfigured,
    loading,
    error,
    load,
  }
}
