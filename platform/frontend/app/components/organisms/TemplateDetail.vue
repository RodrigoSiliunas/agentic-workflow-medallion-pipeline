<template>
  <div class="flex-1 overflow-y-auto">
    <div class="max-w-4xl mx-auto px-8 py-8">
      <!-- Header -->
      <div class="flex items-start gap-4 mb-8">
        <div
          class="w-14 h-14 rounded-[var(--radius-lg)] flex items-center justify-center flex-shrink-0"
          :style="{ background: template.iconBg }"
        >
          <AppIcon :name="template.icon" size="lg" class="text-white" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1.5">
            <TagPill tone="brand">{{ template.category }}</TagPill>
            <TagPill tone="neutral">v{{ template.version }}</TagPill>
            <TagPill v-if="template.deployCount > 20" tone="success">Popular</TagPill>
          </div>
          <h1
            class="text-2xl font-semibold tracking-tight mb-1"
            :style="{ color: 'var(--text-primary)' }"
          >
            {{ template.name }}
          </h1>
          <p class="text-sm" :style="{ color: 'var(--text-secondary)' }">
            {{ template.tagline }}
          </p>
        </div>
        <AppButton :to="`/deploy/${template.slug}`" size="md" icon="i-heroicons-rocket-launch">
          Deploy
        </AppButton>
      </div>

      <!-- Metadata row -->
      <div class="grid grid-cols-3 gap-3 mb-8">
        <div
          class="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] p-3"
        >
          <p class="text-[10px] uppercase tracking-wider" :style="{ color: 'var(--text-tertiary)' }">
            Author
          </p>
          <p class="text-xs font-medium mt-0.5" :style="{ color: 'var(--text-primary)' }">
            {{ template.author }}
          </p>
        </div>
        <div
          class="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] p-3"
        >
          <p class="text-[10px] uppercase tracking-wider" :style="{ color: 'var(--text-tertiary)' }">
            Deploys
          </p>
          <p class="text-xs font-medium mt-0.5" :style="{ color: 'var(--text-primary)' }">
            {{ template.deployCount }} empresas
          </p>
        </div>
        <div
          class="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] p-3"
        >
          <p class="text-[10px] uppercase tracking-wider" :style="{ color: 'var(--text-tertiary)' }">
            Duração estimada
          </p>
          <p class="text-xs font-medium mt-0.5" :style="{ color: 'var(--text-primary)' }">
            {{ template.durationEstimate }}
          </p>
        </div>
      </div>

      <!-- Description -->
      <section class="mb-8">
        <h2 class="text-sm font-semibold mb-2" :style="{ color: 'var(--text-primary)' }">
          Sobre este template
        </h2>
        <p
          class="text-sm leading-relaxed"
          :style="{ color: 'var(--text-secondary)' }"
        >
          {{ template.description }}
        </p>
      </section>

      <!-- Architecture -->
      <section class="mb-8">
        <h2 class="text-sm font-semibold mb-3" :style="{ color: 'var(--text-primary)' }">
          Arquitetura
        </h2>
        <ul
          class="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] divide-y divide-[var(--border)]"
        >
          <li
            v-for="(bullet, idx) in template.architectureBullets"
            :key="idx"
            class="flex items-start gap-3 px-4 py-3 text-sm"
            :style="{ color: 'var(--text-secondary)' }"
          >
            <AppIcon name="chevron-right" size="xs" class="text-[var(--brand-500)] mt-1" />
            {{ bullet }}
          </li>
        </ul>
      </section>

      <!-- Tags -->
      <section class="mb-8">
        <h2 class="text-sm font-semibold mb-3" :style="{ color: 'var(--text-primary)' }">
          Tags
        </h2>
        <div class="flex flex-wrap gap-1.5">
          <TagPill v-for="tag in template.tags" :key="tag" tone="neutral">
            {{ tag }}
          </TagPill>
        </div>
      </section>

      <!-- Changelog -->
      <section>
        <h2 class="text-sm font-semibold mb-3" :style="{ color: 'var(--text-primary)' }">
          Changelog
        </h2>
        <div class="space-y-3">
          <div
            v-for="entry in template.changelog"
            :key="entry.version"
            class="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-4"
          >
            <div class="flex items-center gap-2 mb-2">
              <TagPill tone="brand">v{{ entry.version }}</TagPill>
              <span class="text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
                {{ entry.date }}
              </span>
            </div>
            <ul class="space-y-1 text-xs" :style="{ color: 'var(--text-secondary)' }">
              <li v-for="(change, idx) in entry.changes" :key="idx" class="flex gap-2">
                <span class="text-[var(--brand-500)]">•</span>
                <span>{{ change }}</span>
              </li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Template } from "~/types/template"

defineProps<{ template: Template }>()
</script>
