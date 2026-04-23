<template>
  <div class="space-y-3">
    <div>
      <label class="block text-xs font-medium mb-2" :style="{ color: 'var(--text-secondary)' }">
        Tipo de cluster (driver + worker)
      </label>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
        <button
          v-for="ct in clusterTypes"
          :key="ct.id"
          type="button"
          class="text-left px-3 py-2.5 rounded-[var(--radius-md)] border transition-colors"
          :style="cardStyle(ct.id)"
          @click="selectNode(ct.id)"
        >
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-semibold" :style="{ color: 'var(--text-primary)' }">
              {{ ct.label }}
            </span>
            <span
              class="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
              :style="categoryStyle(ct.category)"
            >
              {{ ct.category }}
            </span>
          </div>
          <div class="text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
            <code>{{ ct.id }}</code>
          </div>
          <div class="flex gap-3 mt-1.5 text-[11px]" :style="{ color: 'var(--text-secondary)' }">
            <span>{{ ct.ramGb }} GB</span>
            <span>{{ ct.vcpu }} vCPU</span>
            <span v-if="ct.localSsdGb > 0">{{ ct.localSsdGb }} GB SSD</span>
          </div>
          <div class="flex gap-3 mt-1 text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
            <span>{{ ct.dbuPerHr }} DBU/h</span>
            <span>${{ ct.instancePricePerHr.toFixed(3) }}/h EC2</span>
          </div>
          <div class="text-[10px] mt-1 italic" :style="{ color: 'var(--text-tertiary)' }">
            {{ ct.useCase }}
          </div>
        </button>
      </div>
    </div>

    <!-- Workers + Spark version -->
    <div class="grid grid-cols-2 gap-3">
      <div>
        <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
          Workers (alem do driver)
        </label>
        <input
          v-model.number="numWorkers"
          type="number"
          min="0"
          max="20"
          class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs"
          :style="{
            background: 'var(--surface)',
            borderColor: 'var(--border)',
            color: 'var(--text-primary)',
          }"
          @input="emitState"
        >
        <p class="text-[10px] mt-1" :style="{ color: 'var(--text-tertiary)' }">
          Total de nodes no cluster = 1 driver + N workers
        </p>
      </div>
      <div>
        <label class="block text-xs font-medium mb-1" :style="{ color: 'var(--text-secondary)' }">
          Databricks Runtime
        </label>
        <select
          v-model="sparkVersion"
          class="w-full px-3 py-2 rounded-[var(--radius-md)] border text-xs"
          :style="{
            background: 'var(--surface)',
            borderColor: 'var(--border)',
            color: 'var(--text-primary)',
          }"
          @change="emitState"
        >
          <option v-for="v in sparkVersions" :key="v.id" :value="v.id">
            {{ v.label }}
          </option>
        </select>
      </div>
    </div>

    <!-- Estimativa custo -->
    <div
      v-if="selectedType"
      class="rounded-[var(--radius-md)] border px-3 py-2.5"
      :style="{
        borderColor: 'var(--border)',
        background: 'rgba(99,102,241,0.08)',
      }"
    >
      <div class="text-xs font-medium mb-1.5" :style="{ color: 'var(--text-primary)' }">
        Estimativa de custo (Premium tier, Jobs Compute)
      </div>
      <div class="grid grid-cols-3 gap-2 text-[11px]" :style="{ color: 'var(--text-secondary)' }">
        <div>
          <div :style="{ color: 'var(--text-tertiary)' }">EC2 (1 driver + {{ numWorkers }} workers)</div>
          <div class="font-mono">{{ formatCost(ec2OnlyCost) }}</div>
        </div>
        <div>
          <div :style="{ color: 'var(--text-tertiary)' }">DBU ({{ totalDbu.toFixed(1) }}/h × ${{ dbuRate }})</div>
          <div class="font-mono">{{ formatCost(dbuOnlyCost) }}</div>
        </div>
        <div>
          <div :style="{ color: 'var(--text-tertiary)' }">Total estimado</div>
          <div class="font-mono font-semibold" :style="{ color: 'var(--brand-400)' }">
            {{ formatCost(totalCost) }}
          </div>
        </div>
      </div>
      <p class="text-[10px] mt-2" :style="{ color: 'var(--text-tertiary)' }">
        Cluster termina automaticamente apos 30min de inatividade. Custo real
        depende do tempo de execucao do pipeline.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useClusterTypes } from "~/composables/useClusterTypes"

interface ClusterPickerState {
  nodeType: string
  numWorkers: number
  sparkVersion: string
}

const props = defineProps<{
  initialNodeType?: string
  initialNumWorkers?: number
  initialSparkVersion?: string
}>()

const emit = defineEmits<{
  "update:state": [state: ClusterPickerState]
}>()

const { clusterTypes, sparkVersions, dbuRate, estimateHourlyCost, formatCost, findById } =
  useClusterTypes()

const selectedNodeType = ref<string>(props.initialNodeType || "m5d.large")
const numWorkers = ref<number>(props.initialNumWorkers ?? 2)
const sparkVersion = ref<string>(props.initialSparkVersion || "15.4.x-scala2.12")

const selectedType = computed(() => findById(selectedNodeType.value))

const totalCost = computed(() =>
  selectedType.value ? estimateHourlyCost(selectedType.value, numWorkers.value) : 0,
)
const ec2OnlyCost = computed(() => {
  if (!selectedType.value) return 0
  return selectedType.value.instancePricePerHr * (1 + numWorkers.value)
})
const dbuOnlyCost = computed(() => totalCost.value - ec2OnlyCost.value)
const totalDbu = computed(() => {
  if (!selectedType.value) return 0
  return selectedType.value.dbuPerHr * (1 + numWorkers.value)
})

function selectNode(id: string) {
  selectedNodeType.value = id
  emitState()
}

function emitState() {
  emit("update:state", {
    nodeType: selectedNodeType.value,
    numWorkers: numWorkers.value,
    sparkVersion: sparkVersion.value,
  })
}

function cardStyle(id: string): Record<string, string> {
  const isActive = selectedNodeType.value === id
  return {
    background: isActive ? "rgba(99,102,241,0.12)" : "var(--surface)",
    borderColor: isActive ? "var(--brand-600)" : "var(--border)",
  }
}

function categoryStyle(cat: string): Record<string, string> {
  const colors: Record<string, string> = {
    general: "rgba(99,102,241,0.15)",
    memory: "rgba(244,114,182,0.15)",
    compute: "rgba(34,197,94,0.15)",
    storage: "rgba(251,191,36,0.15)",
  }
  const text: Record<string, string> = {
    general: "rgb(129,140,248)",
    memory: "rgb(244,114,182)",
    compute: "rgb(34,197,94)",
    storage: "rgb(251,191,36)",
  }
  return { background: colors[cat] || "var(--surface)", color: text[cat] || "var(--text-primary)" }
}

onMounted(() => emitState())
</script>
