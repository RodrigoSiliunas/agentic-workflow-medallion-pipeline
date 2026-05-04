<template>
  <div class="space-y-3">
    <!-- Mode toggle: existing vs new -->
    <div class="grid grid-cols-2 gap-2">
      <button
        type="button"
        class="px-3 py-2 rounded-[var(--radius-md)] border text-xs font-medium transition-colors"
        :style="modeStyle('new')"
        @click="setMode('new')"
      >
        Criar cluster novo
      </button>
      <button
        type="button"
        class="px-3 py-2 rounded-[var(--radius-md)] border text-xs font-medium transition-colors"
        :style="modeStyle('existing')"
        @click="setMode('existing')"
      >
        Usar cluster existente
      </button>
    </div>

    <!-- =========================================================== -->
    <!-- Modo existing: input cluster ID + tags pipeline-level       -->
    <!-- =========================================================== -->
    <div v-if="mode === 'existing'" class="space-y-3">
      <div>
        <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
          Cluster ID *
        </label>
        <input
          v-model.trim="clusterId"
          type="text"
          placeholder="ex: 0421-123456-abc78de9"
          class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs font-mono"
          :style="inputStyle"
          @input="emitState"
        >
        <p class="text-[11px] mt-1" :style="{ color: 'var(--text-tertiary)' }">
          ID do cluster ja existente no workspace alvo. Pega no Databricks UI:
          Compute → cluster → Configuration → ID. Skip auto-detect.
        </p>
      </div>
      <p class="text-[11px] italic" :style="{ color: 'var(--text-tertiary)' }">
        Tags + sizing nao serao alterados — cluster mantem config atual.
      </p>
    </div>

    <!-- =========================================================== -->
    <!-- Modo new                                                     -->
    <!-- =========================================================== -->
    <div v-else class="space-y-3">
      <!-- Cluster mode: ephemeral vs persistent -->
      <div>
        <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
          Modelo de cluster
        </label>
        <div class="grid grid-cols-2 gap-2">
          <button
            type="button"
            class="px-3 py-2 rounded-[var(--radius-md)] border text-xs font-medium transition-colors text-left"
            :style="clusterComputeStyle('ephemeral')"
            @click="setClusterCompute('ephemeral')"
          >
            <div class="font-semibold">Ephemeral (Job Compute)</div>
            <div class="text-[10px] opacity-80 font-normal mt-0.5">
              Cluster criado/destruido por run. ~1/3 DBU. Sem custo idle.
              Cold start ~3min.
            </div>
          </button>
          <button
            type="button"
            class="px-3 py-2 rounded-[var(--radius-md)] border text-xs font-medium transition-colors text-left"
            :style="clusterComputeStyle('persistent')"
            @click="setClusterCompute('persistent')"
          >
            <div class="font-semibold">Persistent (All-purpose)</div>
            <div class="text-[10px] opacity-80 font-normal mt-0.5">
              Cluster reusable, autotermination 30min. DBU 3x maior.
              Warm-start &lt;30s entre runs.
            </div>
          </button>
        </div>
        <p class="text-[10px] mt-1" :style="{ color: 'var(--text-tertiary)' }">
          ETL agendado (1-2x/dia): use Ephemeral. Runs frequentes (hourly+) ou
          notebooks interativos: Persistent.
        </p>
      </div>

      <!-- Nome (so faz sentido em persistent — ephemeral nao tem nome reusavel) -->
      <div v-if="clusterCompute === 'persistent'">
        <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
          Nome do cluster
        </label>
        <input
          v-model.trim="clusterName"
          type="text"
          :placeholder="DEFAULT_NAME"
          class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs font-mono"
          :style="inputStyle"
          @input="emitState"
        >
        <p class="text-[10px] mt-1" :style="{ color: 'var(--text-tertiary)' }">
          Default: <code>{{ DEFAULT_NAME }}</code>. Use nomes diferentes pra coexistir
          multiplos clusters no mesmo workspace.
        </p>
      </div>

      <!-- Tier cards: aplica node_type a worker E driver simultaneamente -->
      <div>
        <label class="block text-xs font-medium mb-2" :style="{ color: 'var(--text-secondary)' }">
          Tier (escolha rapida)
        </label>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <button
            v-for="ct in clusterTypes"
            :key="ct.id"
            type="button"
            class="text-left px-2.5 py-2 rounded-[var(--radius-md)] border transition-colors min-w-0"
            :style="cardStyle(ct.id)"
            @click="selectTier(ct.id)"
          >
            <div class="flex items-center justify-between gap-2 mb-1">
              <span class="text-xs font-semibold truncate" :style="{ color: 'var(--text-primary)' }">
                {{ ct.label }}
              </span>
              <span
                class="text-[10px] px-1.5 py-0.5 rounded-full font-medium flex-shrink-0"
                :style="categoryStyle(ct.category)"
              >
                {{ ct.category }}
              </span>
            </div>
            <div class="text-[10px] truncate" :style="{ color: 'var(--text-tertiary)' }">
              <code>{{ ct.id }}</code>
            </div>
            <div class="flex gap-2 mt-1 text-[10px] flex-wrap" :style="{ color: 'var(--text-secondary)' }">
              <span>{{ ct.ramGb }}GB</span>
              <span>{{ ct.vcpu }}vCPU</span>
              <span class="font-mono">${{ ct.instancePricePerHr.toFixed(3) }}/h</span>
              <span class="font-mono">{{ ct.dbuPerHr }}DBU</span>
            </div>
            <div class="text-[10px] mt-1 italic line-clamp-2" :style="{ color: 'var(--text-tertiary)' }">
              {{ ct.useCase }}
            </div>
            <div
              v-if="ct.warning"
              class="text-[10px] mt-1 px-1.5 py-0.5 rounded line-clamp-2"
              :style="{ background: 'rgba(251,191,36,0.15)', color: 'rgb(251,191,36)' }"
            >
              {{ ct.warning }}
            </div>
          </button>
        </div>
      </div>

      <!-- Avancado accordion: driver split, autoscale, runtime, autoterm, policy -->
      <div
        class="rounded-[var(--radius-md)] border"
        :style="{ borderColor: 'var(--border)' }"
      >
        <button
          type="button"
          class="w-full flex items-center justify-between px-3 py-2 text-xs font-medium"
          :style="{ color: 'var(--text-secondary)' }"
          @click="advancedOpen = !advancedOpen"
        >
          <span class="flex items-center gap-2">
            <AppIcon
              :name="advancedOpen ? 'i-heroicons-chevron-down' : 'i-heroicons-chevron-right'"
              size="xs"
            />
            Sizing avancado
          </span>
          <span class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
            driver/autoscale/runtime/policy
          </span>
        </button>
        <div
          v-if="advancedOpen"
          class="border-t px-3 py-3 space-y-3"
          :style="{ borderColor: 'var(--border)' }"
        >
          <!-- Driver vs worker split -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
                Driver node type
              </label>
              <select v-model="driverNodeType" class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs" :style="inputStyle" @change="emitState">
                <option v-for="ct in clusterTypes" :key="ct.id" :value="ct.id">
                  {{ ct.label }} — {{ ct.id }} ({{ ct.ramGb }}GB)
                </option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
                Worker node type
              </label>
              <select v-model="workerNodeType" class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs" :style="inputStyle" @change="emitState">
                <option v-for="ct in clusterTypes" :key="ct.id" :value="ct.id">
                  {{ ct.label }} — {{ ct.id }} ({{ ct.ramGb }}GB)
                </option>
              </select>
            </div>
          </div>

          <!-- Sizing strategy: fixo vs autoscale -->
          <div>
            <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
              Sizing strategy
            </label>
            <div class="grid grid-cols-2 gap-2">
              <button type="button" class="px-3 py-1.5 rounded-[var(--radius-md)] border text-xs" :style="strategyStyle('fixed')" @click="setStrategy('fixed')">
                Workers fixo
              </button>
              <button type="button" class="px-3 py-1.5 rounded-[var(--radius-md)] border text-xs" :style="strategyStyle('autoscale')" @click="setStrategy('autoscale')">
                Autoscale (min/max)
              </button>
            </div>
            <div v-if="strategy === 'fixed'" class="mt-2">
              <label class="block text-[11px] mb-1" :style="{ color: 'var(--text-tertiary)' }">
                Workers (alem do driver)
              </label>
              <input v-model.number="numWorkers" type="number" min="0" max="20" class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs" :style="inputStyle" @input="emitState">
            </div>
            <div v-else class="grid grid-cols-2 gap-2 mt-2">
              <div>
                <label class="block text-[11px] mb-1" :style="{ color: 'var(--text-tertiary)' }">
                  Min workers
                </label>
                <input v-model.number="autoscaleMin" type="number" min="0" max="20" class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs" :style="inputStyle" @input="emitState">
              </div>
              <div>
                <label class="block text-[11px] mb-1" :style="{ color: 'var(--text-tertiary)' }">
                  Max workers
                </label>
                <input v-model.number="autoscaleMax" type="number" min="1" max="20" class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs" :style="inputStyle" @input="emitState">
              </div>
            </div>
          </div>

          <!-- Spark version + autotermination -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
                Databricks Runtime
              </label>
              <select v-model="sparkVersion" class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs" :style="inputStyle" @change="emitState">
                <option v-for="v in sparkVersions" :key="v.id" :value="v.id">{{ v.label }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
                Auto-terminate (min)
              </label>
              <input v-model.number="autoterminationMin" type="number" min="10" max="240" class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs" :style="inputStyle" @input="emitState">
            </div>
          </div>

          <!-- Cluster policy -->
          <div>
            <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
              Cluster policy
            </label>
            <div class="grid grid-cols-3 gap-1.5 mb-2">
              <button type="button" class="px-2 py-1 rounded-[var(--radius-md)] border text-[11px]" :style="policyModeStyle('none')" @click="setPolicyMode('none')">
                Sem policy
              </button>
              <button type="button" class="px-2 py-1 rounded-[var(--radius-md)] border text-[11px]" :style="policyModeStyle('select')" @click="setPolicyMode('select')">
                Selecionar existente
              </button>
              <button type="button" class="px-2 py-1 rounded-[var(--radius-md)] border text-[11px]" :style="policyModeStyle('custom')" @click="setPolicyMode('custom')">
                JSON custom
              </button>
            </div>

            <!-- Mode: select existing -->
            <div v-if="policyMode === 'select'">
              <div class="flex items-center justify-between mb-1">
                <p class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
                  Policies registradas no workspace (incluindo defaults Databricks):
                </p>
                <button type="button" class="text-[10px] underline" :style="{ color: 'var(--brand-400)' }" @click="loadPolicies">
                  {{ policiesLoading ? "Carregando..." : "Recarregar" }}
                </button>
              </div>
              <select v-model="policyId" class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs" :style="inputStyle" @change="emitState">
                <option value="">— escolha —</option>
                <option v-for="p in policies" :key="p.policy_id" :value="p.policy_id">
                  {{ p.name }}
                </option>
              </select>
              <p v-if="policiesError" class="text-[10px] mt-1" :style="{ color: 'var(--status-error)' }">
                {{ policiesError }}
              </p>
            </div>

            <!-- Mode: custom JSON -->
            <div v-else-if="policyMode === 'custom'">
              <p class="text-[10px] mb-1" :style="{ color: 'var(--text-tertiary)' }">
                JSON da policy (Databricks format). Saga registra policy no workspace
                + atrela ao cluster. Veja
                <a href="https://docs.databricks.com/aws/en/admin/clusters/policy-definition" target="_blank" class="underline" :style="{ color: 'var(--brand-400)' }">
                  docs Databricks
                </a>.
              </p>
              <textarea
                v-model="policyDefinition"
                rows="6"
                placeholder='{"node_type_id":{"type":"allowlist","values":["m5d.large","m5d.xlarge"]},"num_workers":{"type":"range","minValue":1,"maxValue":4},"autotermination_minutes":{"type":"fixed","value":30}}'
                class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-[11px] font-mono"
                :style="inputStyle"
                @input="emitState"
              />
              <p v-if="policyJsonError" class="text-[10px] mt-1" :style="{ color: 'var(--status-error)' }">
                {{ policyJsonError }}
              </p>
            </div>

            <!-- Mode: none -->
            <p v-else class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
              Sem guardrails — qualquer config aceita. Bom pra dev/teste, evite em prod
              multi-team (sem cap de custo nem allowlist).
            </p>
          </div>
        </div>
      </div>

      <!-- Tags -->
      <div>
        <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
          Tags do cluster
        </label>
        <p class="text-[10px] mb-2" :style="{ color: 'var(--text-tertiary)' }">
          Propagadas pra AWS billing (cost allocation tag) + Databricks usage report.
          Use pra rastrear custo por team/cost-center/env.
        </p>
        <div class="space-y-1.5">
          <div v-for="tag in tags" :key="tag.id" class="flex items-center gap-2">
            <input v-model="tag.key" type="text" class="flex-1 px-2 py-1.5 rounded-[var(--radius-md)] border text-xs font-mono" :style="inputStyle" @input="emitState">
            <span :style="{ color: 'var(--text-tertiary)' }">=</span>
            <input v-model="tag.value" type="text" class="flex-1 px-2 py-1.5 rounded-[var(--radius-md)] border text-xs font-mono" :style="inputStyle" @input="emitState">
            <button type="button" class="px-2 py-1.5 rounded-[var(--radius-md)] border text-xs" :style="{ borderColor: 'var(--border)', color: 'var(--status-error)' }" @click="removeTag(tag.id)">
              ×
            </button>
          </div>
          <button type="button" class="px-3 py-1.5 rounded-[var(--radius-md)] border text-xs font-medium" :style="{ borderColor: 'var(--border)', color: 'var(--brand-400)' }" @click="addTag">
            + Adicionar tag
          </button>
        </div>
      </div>

      <!-- Estimativa custo -->
      <div
        v-if="costEstimate"
        class="rounded-[var(--radius-md)] border px-3 py-2.5"
        :style="{ borderColor: 'var(--border)', background: 'rgba(99,102,241,0.08)' }"
      >
        <div class="text-xs font-medium mb-1.5" :style="{ color: 'var(--text-primary)' }">
          Estimativa de custo (Premium tier, Jobs Compute)
        </div>
        <div class="grid grid-cols-3 gap-2 text-[11px]" :style="{ color: 'var(--text-secondary)' }">
          <div>
            <div :style="{ color: 'var(--text-tertiary)' }">EC2 max</div>
            <div class="font-mono">{{ formatCost(costEstimate.ec2MaxPerHr) }}</div>
          </div>
          <div>
            <div :style="{ color: 'var(--text-tertiary)' }">DBU max ({{ costEstimate.totalDbuMax.toFixed(1) }}/h × ${{ dbuRate }})</div>
            <div class="font-mono">{{ formatCost(costEstimate.dbuMaxPerHr) }}</div>
          </div>
          <div>
            <div :style="{ color: 'var(--text-tertiary)' }">Total max</div>
            <div class="font-mono font-semibold" :style="{ color: 'var(--brand-400)' }">{{ formatCost(costEstimate.totalMaxPerHr) }}</div>
          </div>
        </div>
        <div v-if="costEstimate.totalAvgPerHr != null" class="mt-2 text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
          Autoscale ({{ autoscaleMin }}-{{ autoscaleMax }} workers): custo medio estimado
          <span class="font-mono" :style="{ color: 'var(--brand-400)' }">{{ formatCost(costEstimate.totalAvgPerHr) }}</span>
          (depende da carga real)
        </div>
        <p class="text-[10px] mt-2" :style="{ color: 'var(--text-tertiary)' }">
          Cluster termina apos {{ autoterminationMin }}min idle. Custo real depende
          do tempo de execucao do pipeline.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useClusterTypes } from "~/composables/useClusterTypes"
import { useClusterPolicies } from "~/composables/useClusterPolicies"
import { useNodeTypes } from "~/composables/useNodeTypes"

const DEFAULT_NAME = "medallion-pipeline"

interface ClusterPickerState {
  mode: "existing" | "new"
  clusterCompute?: "ephemeral" | "persistent"
  clusterId?: string
  clusterName?: string
  driverNodeType?: string
  workerNodeType?: string
  numWorkers?: number
  autoscaleMin?: number
  autoscaleMax?: number
  sparkVersion?: string
  autoterminationMin?: number
  policyId?: string
  /** JSON da policy custom — saga registra no workspace antes de criar cluster. */
  policyDefinition?: string
  tags?: Record<string, string>
}

const props = defineProps<{
  initialMode?: "existing" | "new"
  initialClusterMode?: "ephemeral" | "persistent"
  initialClusterId?: string
  initialClusterName?: string
  initialNodeType?: string
  initialDriverNodeType?: string
  initialNumWorkers?: number
  initialAutoscaleMin?: number
  initialAutoscaleMax?: number
  initialSparkVersion?: string
  initialAutoterminationMin?: number
  initialPolicyId?: string
  initialPolicyDefinition?: string
  initialTags?: Record<string, string>
}>()

const emit = defineEmits<{
  "update:state": [state: ClusterPickerState]
}>()

const { clusterTypes: rawTypes, sparkVersions, dbuRate, estimateHourlyCost, formatCost, findById } =
  useClusterTypes()
const policiesApi = useClusterPolicies()
const policies = policiesApi.policies
const policiesLoading = policiesApi.loading
const policiesError = policiesApi.error

const nodeTypesApi = useNodeTypes()

// Filtra catalogo curado pra so mostrar tipos suportados pelo workspace.
// Se workspace nao confirmou (sem credentials ou erro), mostra tudo (fallback).
const clusterTypes = computed(() =>
  rawTypes.filter((ct) => nodeTypesApi.isAllowed(ct.id)),
)

const mode = ref<"existing" | "new">(props.initialMode || "new")
const clusterCompute = ref<"ephemeral" | "persistent">(
  props.initialClusterMode || "ephemeral",
)
const clusterId = ref<string>(props.initialClusterId || "")
const clusterName = ref<string>(props.initialClusterName || "")
const workerNodeType = ref<string>(props.initialNodeType || "m5d.large")
const driverNodeType = ref<string>(props.initialDriverNodeType || workerNodeType.value)
const numWorkers = ref<number>(props.initialNumWorkers ?? 2)
const autoscaleMin = ref<number>(props.initialAutoscaleMin ?? 1)
const autoscaleMax = ref<number>(props.initialAutoscaleMax ?? 4)
const sparkVersion = ref<string>(props.initialSparkVersion || "15.4.x-scala2.12")
const autoterminationMin = ref<number>(props.initialAutoterminationMin ?? 30)
const policyId = ref<string>(props.initialPolicyId || "")
const policyDefinition = ref<string>(props.initialPolicyDefinition || "")
const policyMode = ref<"none" | "select" | "custom">(
  props.initialPolicyDefinition
    ? "custom"
    : props.initialPolicyId
      ? "select"
      : "none",
)
const strategy = ref<"fixed" | "autoscale">(
  props.initialAutoscaleMin != null && props.initialAutoscaleMax != null ? "autoscale" : "fixed",
)
// Tags como array com id estavel — usar Record<string,string> faz a key
// servir como :key do v-for, e renomear a chave a cada keystroke desmonta
// o input (foco perdido). Array com id sintetico mantem identidade.
interface TagRow { id: number; key: string; value: string }
let _tagIdSeq = 0
const tags = ref<TagRow[]>(
  Object.entries(props.initialTags || {}).map(([k, v]) => ({
    id: ++_tagIdSeq,
    key: k,
    value: v,
  })),
)
const advancedOpen = ref(false)

const policyJsonError = computed(() => {
  if (policyMode.value !== "custom" || !policyDefinition.value.trim()) return null
  try {
    JSON.parse(policyDefinition.value)
    return null
  } catch (e) {
    return `JSON invalido: ${e instanceof Error ? e.message : "parse error"}`
  }
})

const inputStyle = {
  background: "var(--surface)",
  borderColor: "var(--border)",
  color: "var(--text-primary)",
}

const driverType = computed(() => findById(driverNodeType.value))
const workerType = computed(() => findById(workerNodeType.value))

const costEstimate = computed(() => {
  if (!driverType.value || !workerType.value) return null
  return estimateHourlyCost({
    driver: driverType.value,
    worker: workerType.value,
    numWorkers: strategy.value === "fixed" ? numWorkers.value : undefined,
    autoscaleMin: strategy.value === "autoscale" ? autoscaleMin.value : undefined,
    autoscaleMax: strategy.value === "autoscale" ? autoscaleMax.value : undefined,
  })
})

function selectTier(id: string) {
  workerNodeType.value = id
  driverNodeType.value = id
  emitState()
}

function setMode(next: "existing" | "new") {
  mode.value = next
  emitState()
}

function setClusterCompute(next: "ephemeral" | "persistent") {
  clusterCompute.value = next
  emitState()
}

function clusterComputeStyle(value: "ephemeral" | "persistent"): Record<string, string> {
  const isActive = clusterCompute.value === value
  return {
    background: isActive ? "var(--brand-600)" : "var(--surface)",
    color: isActive ? "white" : "var(--text-secondary)",
    borderColor: isActive ? "var(--brand-600)" : "var(--border)",
  }
}

function setStrategy(next: "fixed" | "autoscale") {
  strategy.value = next
  emitState()
}

function setPolicyMode(next: "none" | "select" | "custom") {
  policyMode.value = next
  emitState()
}

function policyModeStyle(value: "none" | "select" | "custom"): Record<string, string> {
  const isActive = policyMode.value === value
  return {
    background: isActive ? "var(--brand-600)" : "var(--surface)",
    color: isActive ? "white" : "var(--text-secondary)",
    borderColor: isActive ? "var(--brand-600)" : "var(--border)",
  }
}

function emitState() {
  if (mode.value === "existing") {
    emit("update:state", { mode: "existing", clusterId: clusterId.value })
    return
  }
  const payload: ClusterPickerState = {
    mode: "new",
    clusterCompute: clusterCompute.value,
    clusterName: clusterName.value || undefined,
    driverNodeType: driverNodeType.value,
    workerNodeType: workerNodeType.value,
    sparkVersion: sparkVersion.value,
    autoterminationMin: autoterminationMin.value,
    tags: tagsToRecord(),
  }
  if (policyMode.value === "select") {
    payload.policyId = policyId.value || undefined
  } else if (policyMode.value === "custom") {
    payload.policyDefinition = policyDefinition.value || undefined
  }
  if (strategy.value === "fixed") {
    payload.numWorkers = numWorkers.value
  } else {
    payload.autoscaleMin = autoscaleMin.value
    payload.autoscaleMax = autoscaleMax.value
  }
  emit("update:state", payload)
}

function modeStyle(value: "existing" | "new"): Record<string, string> {
  const isActive = mode.value === value
  return {
    background: isActive ? "var(--brand-600)" : "var(--surface)",
    color: isActive ? "white" : "var(--text-secondary)",
    borderColor: isActive ? "var(--brand-600)" : "var(--border)",
  }
}

function strategyStyle(value: "fixed" | "autoscale"): Record<string, string> {
  const isActive = strategy.value === value
  return {
    background: isActive ? "var(--brand-600)" : "var(--surface)",
    color: isActive ? "white" : "var(--text-secondary)",
    borderColor: isActive ? "var(--brand-600)" : "var(--border)",
  }
}

function cardStyle(id: string): Record<string, string> {
  const isActive = workerNodeType.value === id
  return {
    background: isActive ? "rgba(99,102,241,0.12)" : "var(--surface)",
    borderColor: isActive ? "var(--brand-600)" : "var(--border)",
  }
}

function categoryStyle(cat: string): Record<string, string> {
  const colors: Record<string, string> = {
    micro: "rgba(251,191,36,0.15)",
    general: "rgba(99,102,241,0.15)",
    memory: "rgba(244,114,182,0.15)",
    compute: "rgba(34,197,94,0.15)",
    storage: "rgba(251,191,36,0.15)",
  }
  const text: Record<string, string> = {
    micro: "rgb(251,191,36)",
    general: "rgb(129,140,248)",
    memory: "rgb(244,114,182)",
    compute: "rgb(34,197,94)",
    storage: "rgb(251,191,36)",
  }
  return { background: colors[cat] || "var(--surface)", color: text[cat] || "var(--text-primary)" }
}

function addTag() {
  tags.value.push({ id: ++_tagIdSeq, key: `tag${tags.value.length + 1}`, value: "" })
  emitState()
}

function removeTag(id: number) {
  tags.value = tags.value.filter(t => t.id !== id)
  emitState()
}

function tagsToRecord(): Record<string, string> | undefined {
  const out: Record<string, string> = {}
  for (const t of tags.value) {
    const k = t.key.trim()
    if (!k) continue
    out[k] = t.value
  }
  return Object.keys(out).length ? out : undefined
}

async function loadPolicies() {
  await policiesApi.load()
}

onMounted(() => {
  loadPolicies()
  nodeTypesApi.load()
  emitState()
})
</script>
