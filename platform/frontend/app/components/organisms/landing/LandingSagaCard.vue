<template>
  <LandingCardShell
    eyebrow="Deploy em tempo real"
    title="Saga com 10 etapas atômicas e logs em streaming"
    description="Cada deploy provisiona AWS + Databricks em 10 passos. Você vê tudo ao vivo via SSE sem precisar abrir terminal."
  >
    <!-- Fake window chrome -->
    <div
      class="mx-6 mb-6 rounded-[var(--radius-md)] border overflow-hidden"
      :style="{ borderColor: 'var(--border)', background: 'var(--bg)' }"
    >
      <!-- Chrome header -->
      <div
        class="flex items-center gap-2 px-3 py-2 border-b"
        :style="{ borderColor: 'var(--border)', background: 'var(--surface-elevated)' }"
      >
        <div class="flex gap-1">
          <span class="w-2 h-2 rounded-full bg-[#ff5f57]" />
          <span class="w-2 h-2 rounded-full bg-[#febc2e]" />
          <span class="w-2 h-2 rounded-full bg-[#28c840]" />
        </div>
        <div
          class="flex-1 mx-4 text-[10px] font-[var(--font-mono)] truncate text-center"
          :style="{ color: 'var(--text-tertiary)' }"
        >
          /deployments/dep-5f9e2
        </div>
        <span
          class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-sm font-medium"
          :style="{
            background: 'rgba(127, 34, 254, 0.12)',
            color: 'var(--brand-400)',
          }"
        >
          <span
            class="w-1 h-1 rounded-full status-pulse"
            :style="{ background: 'var(--brand-400)' }"
          />
          LIVE
        </span>
      </div>

      <!-- Two-column body: saga steps + log stream -->
      <div class="grid grid-cols-2 divide-x" :style="{ borderColor: 'var(--border)' }">
        <!-- LEFT: saga steps -->
        <div class="p-3 space-y-1.5">
          <div
            v-for="(step, idx) in steps"
            :key="step.id"
            class="flex items-center gap-2 text-[11px]"
          >
            <!-- Status icon -->
            <div
              class="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
              :style="{ background: iconBg(step.status) }"
            >
              <svg
                v-if="step.status === 'success'"
                viewBox="0 0 20 20"
                fill="white"
                class="w-2.5 h-2.5"
              >
                <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
              </svg>
              <span
                v-else-if="step.status === 'running'"
                class="w-1.5 h-1.5 rounded-full bg-white status-pulse"
              />
              <span
                v-else
                class="text-[8px]"
                :style="{ color: 'var(--text-tertiary)' }"
              >{{ idx + 1 }}</span>
            </div>
            <span
              class="flex-1 font-[var(--font-mono)] truncate"
              :style="{
                color:
                  step.status === 'pending'
                    ? 'var(--text-tertiary)'
                    : 'var(--text-secondary)',
              }"
            >{{ step.label }}</span>
            <span
              v-if="step.duration"
              class="tabular-nums text-[10px]"
              :style="{ color: 'var(--text-tertiary)' }"
            >{{ step.duration }}</span>
          </div>
        </div>

        <!-- RIGHT: log stream (monospace) -->
        <div class="p-3 space-y-0.5 overflow-hidden max-h-[220px]">
          <div
            v-for="(log, idx) in visibleLogs"
            :key="idx"
            class="flex items-start gap-1.5 text-[10px] font-[var(--font-mono)] leading-relaxed"
          >
            <span
              class="tabular-nums flex-shrink-0"
              :style="{ color: 'var(--text-tertiary)' }"
            >{{ log.time }}</span>
            <span
              class="flex-1 truncate"
              :style="{ color: log.color }"
            >{{ log.msg }}</span>
          </div>
        </div>
      </div>
    </div>
  </LandingCardShell>
</template>

<script setup lang="ts">
interface Step {
  id: string
  label: string
  status: "success" | "running" | "pending"
  duration?: string
}

const steps: Step[] = [
  { id: "validate", label: "Validate credentials", status: "success", duration: "2.2s" },
  { id: "s3", label: "Create S3 bucket", status: "success", duration: "1.8s" },
  { id: "iam", label: "IAM role + policy", status: "success", duration: "1.2s" },
  { id: "secrets", label: "Databricks secrets", status: "success", duration: "2.1s" },
  { id: "catalog", label: "Setup Unity Catalog", status: "running" },
  { id: "upload", label: "Upload notebooks", status: "pending" },
  { id: "workflow", label: "Create workflow", status: "pending" },
  { id: "observer", label: "Deploy Observer", status: "pending" },
  { id: "trigger", label: "Trigger first run", status: "pending" },
  { id: "register", label: "Register pipeline", status: "pending" },
]

interface Log {
  time: string
  msg: string
  color: string
}

const ALL_LOGS: Log[] = [
  { time: "00:12", msg: "Calling AWS STS...", color: "var(--text-secondary)" },
  { time: "00:13", msg: "✓ Credentials OK", color: "var(--status-success)" },
  { time: "00:14", msg: "terraform apply...", color: "var(--text-secondary)" },
  { time: "00:16", msg: "✓ Bucket created", color: "var(--status-success)" },
  { time: "00:17", msg: "Attaching IAM policy", color: "var(--text-secondary)" },
  { time: "00:18", msg: "✓ Role provisioned", color: "var(--status-success)" },
  { time: "00:19", msg: "Uploading secrets", color: "var(--text-secondary)" },
  { time: "00:20", msg: "✓ Scope ready", color: "var(--status-success)" },
  { time: "00:21", msg: "CREATE CATALOG medallion", color: "var(--brand-400)" },
  { time: "00:22", msg: "CREATE SCHEMA bronze", color: "var(--brand-400)" },
]

// Log streaming animado — adiciona uma linha por vez
const visibleLogs = ref<Log[]>([])

function cycleLogs() {
  let i = 0
  const push = () => {
    if (i < ALL_LOGS.length) {
      visibleLogs.value = [...visibleLogs.value, ALL_LOGS[i]!].slice(-8)
      i++
      setTimeout(push, 450)
    } else {
      // Reset e recomeça depois de 3s
      setTimeout(() => {
        visibleLogs.value = []
        i = 0
        push()
      }, 2500)
    }
  }
  push()
}

onMounted(() => {
  if (import.meta.client) cycleLogs()
})

function iconBg(status: Step["status"]): string {
  switch (status) {
    case "success":
      return "var(--status-success)"
    case "running":
      return "var(--brand-600)"
    default:
      return "var(--surface-elevated)"
  }
}
</script>
