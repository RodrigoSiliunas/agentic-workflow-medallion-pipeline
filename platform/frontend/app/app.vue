<template>
  <div class="min-h-screen bg-[var(--bg)] text-[var(--text-primary)] font-[var(--font-sans)]">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </div>
</template>

<script setup lang="ts">
// Forca dark mode como default. O usuario pode alternar no futuro
// via toggle de tema, mas o brand Namastex eh dark-first.
const colorMode = useColorMode()
onMounted(() => {
  if (!colorMode.preference || colorMode.preference === "system") {
    colorMode.preference = "dark"
  }
})

useHead({
  title: "Namastex Platform",
  meta: [
    {
      name: "description",
      content:
        "Plataforma agentic de pipelines de dados — Bronze, Silver, Gold com agente AI autonomo.",
    },
  ],
  link: [{ rel: "icon", type: "image/svg+xml", href: "/favicon.svg" }],
})
</script>
