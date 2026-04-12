<template>
  <UIcon
    :name="resolvedName"
    :class="['inline-block flex-shrink-0 align-middle', props.class]"
    :style="sizeStyle"
  />
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    name: string
    size?: "xs" | "sm" | "md" | "lg" | "xl"
    collection?: string
    class?: string
  }>(),
  {
    size: "md",
    collection: "heroicons",
    class: undefined,
  },
)

const resolvedName = computed(() => {
  if (props.name.startsWith("i-")) return props.name
  return `i-${props.collection}-${props.name}`
})

// Iconify renderiza via `<span class="iconify">` com dimensoes de `1em x 1em`
// definidas em `:where(.iconify)` (specificity zero). Inline style vence
// qualquer CSS externo — mais seguro que classes Tailwind (algumas versoes
// do NuxtUI+Iconify nao respeitam w-*/h-* dependendo da ordem do cascade).
// Tambem forca `inline-block` caso alguma regra resete pra `display: inline`
// (width/height sao ignorados em inline).
const PX: Record<string, number> = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 20,
  xl: 24,
}

const sizeStyle = computed(() => {
  const px = PX[props.size] ?? PX.md
  return {
    width: `${px}px`,
    height: `${px}px`,
    minWidth: `${px}px`,
    minHeight: `${px}px`,
    fontSize: `${px}px`,
  }
})
</script>
