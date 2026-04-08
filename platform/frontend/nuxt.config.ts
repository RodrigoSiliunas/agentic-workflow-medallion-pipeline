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

  // API backend (FastAPI)
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1",
    },
  },

  // Nuxt UI color config
  ui: {
    colorMode: true,
  },

  // Image optimization
  image: {
    quality: 80,
    formats: ["webp", "avif"],
  },
})
