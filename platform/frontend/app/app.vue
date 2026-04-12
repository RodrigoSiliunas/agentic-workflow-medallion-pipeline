<template>
  <div class="min-h-screen bg-[var(--bg)] text-[var(--text-primary)] font-[var(--font-sans)]">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </div>
</template>

<script setup lang="ts">
// Força dark mode como default. O usuário pode alternar no futuro
// via toggle de tema, mas o brand Safatechx é dark-first.
const colorMode = useColorMode()
onMounted(() => {
  if (!colorMode.preference || colorMode.preference === "system") {
    colorMode.preference = "dark"
  }
})

useHead({
  title: "Safatechx Platform",
  meta: [
    {
      name: "description",
      content:
        "Plataforma agêntica de pipelines de dados — Bronze, Silver, Gold com agente AI autônomo.",
    },
  ],
  link: [{ rel: "icon", type: "image/svg+xml", href: "/favicon.svg" }],
})
</script>
