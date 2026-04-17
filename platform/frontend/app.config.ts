/**
 * Nuxt UI app config — define a paleta primaria como `flowertex`
 * (purple Flowertex Labs) e gray como zinc para alinhar com os tokens
 * CSS em assets/css/main.css.
 *
 * Os componentes do @nuxt/ui que aceitam `color="primary"` vao usar
 * automaticamente a escala flowertex (50→900) configurada via CSS
 * variables `--brand-*`.
 */
export default defineAppConfig({
  ui: {
    colors: {
      primary: "flowertex",
      neutral: "zinc",
    },
    button: {
      defaultVariants: {
        color: "primary",
        size: "md",
      },
    },
    card: {
      slots: {
        root: "rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)]",
        body: "p-4",
      },
    },
  },
})
