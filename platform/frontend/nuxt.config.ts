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

  // API backend (FastAPI) — usado quando saimos do mock mode
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1",
      // Mock mode: quando true, stores e composables retornam dados ficticios
      // sem chamar o backend. Default true ate o backend estar pronto.
      mockMode: process.env.NUXT_PUBLIC_MOCK_MODE !== "false",
    },
  },

  // Nuxt UI color config — primary aponta pra paleta Namastex (definida em app.config.ts)
  ui: {
    colorMode: true,
  },

  // Geist font (sans + mono) — design system Namastex
  fonts: {
    families: [
      { name: "Geist", provider: "google", weights: [300, 400, 500, 600, 700] },
      { name: "Geist Mono", provider: "google", weights: [400, 500] },
    ],
  },

  // Image optimization
  image: {
    quality: 80,
    formats: ["webp", "avif"],
  },
})
