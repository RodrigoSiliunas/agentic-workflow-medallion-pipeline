/**
 * Deployments store — saga mockada para one-click deploy.
 * runSaga simula cada etapa com setTimeout e emite logs reativos.
 * Quando o backend real (Celery + Terraform + Databricks SDK) chegar,
 * trocar runSaga por fetch/SSE para o endpoint.
 *
 * Mock branching foi movido para useDeploymentsApi (Strategy pattern).
 * O store so faz branching em runSaga (SSE mock vs real sao fluxos distintos).
 */
import { defineStore } from "pinia"
import type {
  Deployment,
  DeploymentConfig,
  LogLevel,
} from "~/types/deployment"
import { emitLog, runSagaMock } from "~/composables/mock/deployments"

export const useDeploymentsStore = defineStore("deployments", () => {
  const config = useRuntimeConfig()
  const isMock = computed(() => Boolean(config.public.mockMode))

  const deployments = ref<Deployment[]>([])
  const loaded = ref(false)
  const loading = ref(false)

  // subscribes ativos (SSE)
  const subscribers = new Map<string, () => void>()

  const list = computed(() =>
    [...deployments.value].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    ),
  )

  async function load(force = false) {
    if (loaded.value && !force) return
    loading.value = true
    try {
      const api = useDeploymentsApi()
      deployments.value = await api.list()
      loaded.value = true
    } catch (e) {
      console.error("Failed to load deployments", e)
      deployments.value = []
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  async function loadBlueprint() {
    const api = useDeploymentsApi()
    return api.getBlueprint()
  }

  async function refreshOne(id: string) {
    const api = useDeploymentsApi()
    const fresh = await api.getById(id)
    if (!fresh) return
    const idx = deployments.value.findIndex((d) => d.id === id)
    if (idx >= 0) {
      deployments.value[idx] = fresh
    } else {
      deployments.value.unshift(fresh)
    }
  }

  function getById(id: string): Deployment | undefined {
    return deployments.value.find((d) => d.id === id)
  }

  async function createDeployment(
    templateSlug: string,
    templateName: string,
    cfg: DeploymentConfig,
  ): Promise<Deployment> {
    const api = useDeploymentsApi()
    const created = await api.create(templateSlug, cfg)
    // O composable mock nao sabe o templateName real — corrigimos aqui
    created.templateName = templateName
    deployments.value.unshift(created)
    return created
  }

  // runSaga mantem isMock branching: SSE real e mock sao fluxos totalmente distintos.
  async function runSaga(deploymentId: string): Promise<void> {
    const deployment = getById(deploymentId)
    if (!deployment) return
    if (deployment.status === "running" || deployment.status === "success") return

    if (isMock.value) {
      await runSagaMock(deployment)
      return
    }

    // Backend real: connect SSE e atualiza state conforme os eventos chegam
    const api = useDeploymentsApi()
    if (subscribers.has(deploymentId)) return // ja subscrito

    const unsubscribe = api.subscribeEvents(deploymentId, {
      onStep: (stepId, status, durationMs) => {
        const step = deployment.steps.find((s) => s.id === stepId)
        if (!step) return
        step.status = status as typeof step.status
        if (durationMs) step.durationMs = durationMs
      },
      onLog: (log) => {
        deployment.logs.push(log)
      },
      onStatusChange: (status) => {
        deployment.status = status as Deployment["status"]
      },
      onComplete: async () => {
        await refreshOne(deploymentId)
        unsubscribe()
        subscribers.delete(deploymentId)
      },
      onError: (msg) => {
        console.error("SSE error", msg)
        unsubscribe()
        subscribers.delete(deploymentId)
      },
    })
    subscribers.set(deploymentId, unsubscribe)
  }

  async function cancel(id: string) {
    const d = getById(id)
    if (!d) return
    const api = useDeploymentsApi()
    await api.cancel(id)
    // Em mock mode, o composable retorna sem side-effect — marcamos localmente
    if (isMock.value && d.status === "running") {
      d.status = "cancelled"
      emitLog(d, "warn" as LogLevel, "Deployment cancelled by user")
    }
    const unsubscribe = subscribers.get(id)
    unsubscribe?.()
    subscribers.delete(id)
  }

  async function deleteDeployment(id: string) {
    const api = useDeploymentsApi()
    await api.remove(id)
    deployments.value = deployments.value.filter((d) => d.id !== id)
  }

  return {
    deployments,
    list,
    loaded,
    loading,
    load,
    loadBlueprint,
    refreshOne,
    getById,
    createDeployment,
    runSaga,
    cancel,
    deleteDeployment,
  }
})
