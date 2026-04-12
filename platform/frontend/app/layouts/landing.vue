<template>
  <div
    class="min-h-screen relative overflow-x-hidden"
    :style="{ background: 'var(--bg)', color: 'var(--text-primary)' }"
  >
    <slot />
  </div>
</template>

<script setup lang="ts">
// Layout dedicado da landing — sem sidebar, dark-first, full-bleed.
// Força dark mode para manter a signature Safatechx.
const colorMode = useColorMode()
onMounted(() => {
  colorMode.preference = "dark"
})
</script>
