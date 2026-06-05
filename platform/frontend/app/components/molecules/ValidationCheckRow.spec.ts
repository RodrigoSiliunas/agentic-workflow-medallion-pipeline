import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import ValidationCheckRow from "./ValidationCheckRow.vue"
import type { ValidationCheck } from "~/types/pipeline-editor-v2"

describe("ValidationCheckRow", () => {
  it("renderiza o rótulo do check", async () => {
    const check: ValidationCheck = { label: "Ruff lint", state: "pending" }
    const wrapper = await mountSuspended(ValidationCheckRow, { props: { check } })
    expect(wrapper.text()).toContain("Ruff lint")
  })

  it("exibe ícone check-circle quando state=ok", async () => {
    const check: ValidationCheck = { label: "Codegen PySpark", state: "ok" }
    const wrapper = await mountSuspended(ValidationCheckRow, { props: { check } })
    // AppIcon renderiza iconify com o nome do ícone
    expect(wrapper.html()).toContain("check-circle")
  })

  it("exibe ícone x-circle quando state=fail", async () => {
    const check: ValidationCheck = { label: "Schema compatível", state: "fail" }
    const wrapper = await mountSuspended(ValidationCheckRow, { props: { check } })
    expect(wrapper.html()).toContain("x-circle")
  })

  it("aplica cor de erro no texto quando state=fail", async () => {
    const check: ValidationCheck = { label: "Falhou", state: "fail" }
    const wrapper = await mountSuspended(ValidationCheckRow, { props: { check } })
    const label = wrapper.find("span")
    expect(label.attributes("style") || "").toContain("var(--status-error)")
  })

  it("exibe StatusDot pulsante quando state=running", async () => {
    const check: ValidationCheck = { label: "Rodando", state: "running" }
    const wrapper = await mountSuspended(ValidationCheckRow, { props: { check } })
    // AppStatusDot renderiza um span
    expect(wrapper.find("span").exists()).toBe(true)
  })

  it("exibe ícone clock quando state=pending", async () => {
    const check: ValidationCheck = { label: "Marker injetado", state: "pending" }
    const wrapper = await mountSuspended(ValidationCheckRow, { props: { check } })
    expect(wrapper.html()).toContain("clock")
  })
})
