<template>
  <LandingCardShell>
    <div class="px-8 py-8 grid grid-cols-1 md:grid-cols-5 gap-8 md:gap-10">
      <!-- Left: headline + CTA -->
      <div class="md:col-span-2 flex flex-col justify-between">
        <h3
          class="text-2xl sm:text-[28px] leading-[1.08] tracking-tight max-w-[14ch]"
          :style="{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-display)',
            fontWeight: 400,
          }"
        >
          Muito mais que pipelines e agentes.
        </h3>

        <NuxtLink
          to="/register"
          class="inline-flex items-center gap-2 mt-6 md:mt-10 text-[11px] uppercase tracking-[0.22em] font-semibold group/link self-start"
          :style="{ color: 'var(--brand-400)' }"
        >
          <span>Explorar tudo</span>
          <span
            class="inline-block transition-transform duration-300 group-hover/link:translate-x-1"
          >→</span>
        </NuxtLink>
      </div>

      <!-- Right: grid 2x? with features -->
      <div class="md:col-span-3 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
        <div
          v-for="feature in features"
          :key="feature.label"
          class="flex items-center gap-2.5 py-1"
        >
          <AppIcon
            :name="feature.icon"
            size="sm"
            :style="{ color: 'var(--text-tertiary)' }"
          />
          <span
            class="text-sm leading-tight"
            :style="{ color: 'var(--text-secondary)' }"
          >{{ feature.label }}</span>
        </div>
      </div>
    </div>
  </LandingCardShell>
</template>

<script setup lang="ts">
interface Feature {
  label: string
  icon: string
}

const features: Feature[] = [
  { label: "Slash commands", icon: "hashtag" },
  { label: "Webhooks HMAC", icon: "shield-check" },
  { label: "Schema evolution", icon: "arrow-path" },
  { label: "Dedup de diagnósticos", icon: "cpu-chip" },
  { label: "Dry-run mode", icon: "eye" },
  { label: "Multi-file fixes", icon: "document-text" },
  { label: "Feedback loop", icon: "arrow-uturn-left" },
  { label: "RBAC multi-tenant", icon: "users" },
  { label: "Controle de custos", icon: "currency-dollar" },
  { label: "Rollback Delta", icon: "arrow-trending-down" },
]
</script>
