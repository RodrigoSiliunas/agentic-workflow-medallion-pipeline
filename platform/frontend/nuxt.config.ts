export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },

  future: {
    compatibilityVersion: 4,
  },

  modules: [
    "@nuxt/ui",
    "@nuxt/icon",
    "@nuxt/image",
    "@nuxt/fonts",
    "@nuxt/eslint",
    "@pinia/nuxt",
    "@vueuse/nuxt",
  ],

  css: ["~/assets/css/main.css"],

  // Atomic Design: registra todos os componentes pelo nome do arquivo
  // (sem prefixo de pasta). Sem isso, `atoms/AppIcon.vue` vira `AtomsAppIcon`
  // e `<AppIcon>` no template fica "Failed to resolve component".
  components: [
    { path: "~/components/atoms", pathPrefix: false },
    { path: "~/components/molecules", pathPrefix: false },
    { path: "~/components/organisms/landing", pathPrefix: false },
    { path: "~/components/organisms", pathPrefix: false },
    { path: "~/components/templates", pathPrefix: false },
  ],

  // API backend (FastAPI) — usado quando saimos do mock mode
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1",
      // Mock mode: quando true, stores e composables retornam dados ficticios
      // sem chamar o backend. Default true para facilitar dev offline.
      // Para conectar no backend real, setar NUXT_PUBLIC_MOCK_MODE=false.
      mockMode: process.env.NUXT_PUBLIC_MOCK_MODE !== "false",
    },
  },

  // Nuxt UI color config — primary aponta pra paleta Safatechx (definida em app.config.ts)
  ui: {
    colorMode: true,
  },

  // Geist font (sans + mono) — design system Safatechx
  fonts: {
    families: [
      { name: "Geist", provider: "google", weights: [300, 400, 500, 600, 700] },
      { name: "Geist Mono", provider: "google", weights: [400, 500] },
      // Serif display para headlines elegantes (estilo ngrok / safatechx.com)
      { name: "Instrument Serif", provider: "google", weights: [400], italic: true },
    ],
  },

  // Image optimization
  image: {
    quality: 80,
    formats: ["webp", "avif"],
  },

  // Pre-bundle das deps do Vue Devtools — elimina o reload automatico do Vite
  // quando ele descobre esses modulos em runtime e precisa reotimizar.
  vite: {
    optimizeDeps: {
      include: ["@vue/devtools-core", "@vue/devtools-kit"],
    },
  },
})
