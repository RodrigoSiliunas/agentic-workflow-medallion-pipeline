<template>
  <div
    ref="cardRef"
    class="landing-card"
    @mousemove="onMouseMove"
    @mouseleave="onMouseLeave"
  >
    <!-- Top accent line -->
    <div class="landing-card__top-accent" />

    <!-- Content -->
    <div class="landing-card__content">
      <!-- Header (eyebrow + title + description) -->
      <div v-if="eyebrow || title || description" class="px-6 pt-6 pb-4">
        <p
          v-if="eyebrow"
          class="text-[10px] uppercase tracking-[0.22em] font-semibold mb-3"
          :style="{ color: 'var(--brand-400)' }"
        >
          {{ eyebrow }}
        </p>
        <h3
          v-if="title"
          class="text-xl sm:text-2xl tracking-tight leading-[1.1]"
          :style="{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-display)',
            fontWeight: 400,
          }"
        >
          {{ title }}
        </h3>
        <p
          v-if="description"
          class="text-xs mt-2 max-w-md leading-relaxed"
          :style="{ color: 'var(--text-secondary)' }"
        >
          {{ description }}
        </p>
      </div>

      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  eyebrow?: string
  title?: string
  description?: string
}>()

const cardRef = ref<HTMLElement | null>(null)

function onMouseMove(e: MouseEvent) {
  const el = cardRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  el.style.setProperty("--mx", `${x}px`)
  el.style.setProperty("--my", `${y}px`)
  el.style.setProperty("--glow-opacity", "1")
}

function onMouseLeave() {
  const el = cardRef.value
  if (!el) return
  el.style.setProperty("--glow-opacity", "0")
}
</script>

<style scoped>
.landing-card {
  position: relative;
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--border);
  overflow: hidden;
  isolation: isolate;
  transition: border-color 0.3s ease;
  --mx: 50%;
  --my: 50%;
  --glow-opacity: 0;
}

/* Inner spotlight — radial glow suave atrás do conteúdo */
.landing-card::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  z-index: 0;
  background: radial-gradient(
    600px circle at var(--mx) var(--my),
    rgba(127, 34, 254, 0.1),
    transparent 45%
  );
  opacity: var(--glow-opacity);
  transition: opacity 0.4s ease;
}

/* Border glow — mask trick pra iluminar só a borda */
.landing-card::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  z-index: 1;
  padding: 1px;
  background: radial-gradient(
    400px circle at var(--mx) var(--my),
    rgba(127, 34, 254, 0.7),
    rgba(127, 34, 254, 0.2) 15%,
    transparent 40%
  );
  -webkit-mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  opacity: var(--glow-opacity);
  transition: opacity 0.4s ease;
}

/* Top accent line — acende no hover */
.landing-card__top-accent {
  position: absolute;
  top: 0;
  inset-inline: 0;
  height: 1px;
  pointer-events: none;
  z-index: 2;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(127, 34, 254, 0.4),
    transparent
  );
  opacity: 0.5;
  transition: opacity 0.4s ease;
}

.landing-card:hover .landing-card__top-accent {
  opacity: 1;
}

.landing-card__content {
  position: relative;
  z-index: 2;
}
</style>
