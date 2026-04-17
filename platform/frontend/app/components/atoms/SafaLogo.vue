<template>
  <component
    :is="to ? 'NuxtLink' : 'span'"
    :to="to"
    :class="['safa-logo', glow ? 'safa-logo--glow' : '']"
    :style="{ color: resolvedColor }"
  >
    <!-- Icon: aperture/shutter com 6 blades rotacionadas -->
    <svg
      v-if="variant !== 'wordmark'"
      class="safa-logo__icon"
      :width="iconSize"
      :height="iconSize"
      viewBox="0 0 48 48"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <!-- Blade base — curva de pétala, todas identicas rotacionadas 60° -->
        <path
          id="safa-blade"
          d="M 24 4 Q 31 10 30 19 Q 30 23 26 23 Q 23 21 23 14 Q 22 9 24 4 Z"
        />
      </defs>
      <g>
        <use href="#safa-blade" />
        <use href="#safa-blade" transform="rotate(60 24 24)" />
        <use href="#safa-blade" transform="rotate(120 24 24)" />
        <use href="#safa-blade" transform="rotate(180 24 24)" />
        <use href="#safa-blade" transform="rotate(240 24 24)" />
        <use href="#safa-blade" transform="rotate(300 24 24)" />
      </g>
      <!-- Centro vazio: pequeno circulo com fill do background pra furar o centro -->
      <circle cx="24" cy="24" r="3" fill="var(--bg, #090a0b)" />
    </svg>

    <!-- Wordmark: "Flowertex" em Geist via <text> (usa font ja carregada) -->
    <svg
      v-if="variant !== 'icon'"
      class="safa-logo__wordmark"
      :height="wordmarkHeight"
      viewBox="0 0 180 36"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Flowertex"
    >
      <text
        x="0"
        y="27"
        fill="currentColor"
        font-family="Geist, Inter, system-ui, -apple-system, sans-serif"
        font-size="28"
        font-weight="600"
        letter-spacing="-0.8"
      >Flowertex</text>
    </svg>
  </component>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    variant?: "icon" | "wordmark" | "lockup"
    size?: number
    glow?: boolean
    color?: string
    to?: string
  }>(),
  {
    variant: "lockup",
    size: 28,
    glow: false,
    color: undefined,
    to: undefined,
  },
)

const iconSize = computed(() => props.size)
const wordmarkHeight = computed(() => Math.round(props.size * 0.9))
const resolvedColor = computed(() => props.color ?? "var(--brand-500)")
</script>

<style scoped>
.safa-logo {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  color: inherit;
  transition: transform 0.3s ease;
}

.safa-logo:hover {
  transform: translateY(-1px);
}

.safa-logo__icon {
  flex-shrink: 0;
  display: block;
}

.safa-logo__wordmark {
  width: auto;
  flex-shrink: 0;
  display: block;
}

/* Variante com glow purple pulsante (pra hero/CTAs) */
.safa-logo--glow .safa-logo__icon {
  filter: drop-shadow(0 0 8px rgba(127, 34, 254, 0.5))
    drop-shadow(0 0 20px rgba(127, 34, 254, 0.3));
  animation: safa-glow-pulse 3.5s ease-in-out infinite;
}

@keyframes safa-glow-pulse {
  0%,
  100% {
    filter: drop-shadow(0 0 8px rgba(127, 34, 254, 0.5))
      drop-shadow(0 0 20px rgba(127, 34, 254, 0.3));
  }
  50% {
    filter: drop-shadow(0 0 12px rgba(127, 34, 254, 0.7))
      drop-shadow(0 0 28px rgba(127, 34, 254, 0.5));
  }
}
</style>
