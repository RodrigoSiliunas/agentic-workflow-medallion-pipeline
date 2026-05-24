import { defineVitestConfig } from "@nuxt/test-utils/config"

export default defineVitestConfig({
  test: {
    environment: "nuxt",
    globals: true,
    include: ["app/**/*.{spec,test}.ts"],
    environmentOptions: {
      nuxt: {
        overrides: {
          ssr: false,
        },
      },
    },
  },
})
