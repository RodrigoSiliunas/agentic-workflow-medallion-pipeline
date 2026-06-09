import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import AppSelect from "./AppSelect.vue"

const OPTIONS = [
  { value: "a", label: "Opção A" },
  { value: "b", label: "Opção B" },
]

describe("AppSelect", () => {
  it("renderiza as opções passadas", async () => {
    const wrapper = await mountSuspended(AppSelect, { props: { options: OPTIONS } })
    expect(wrapper.html()).toContain("Opção A")
    expect(wrapper.html()).toContain("Opção B")
  })

  it("seleciona o valor inicial via modelValue", async () => {
    const wrapper = await mountSuspended(AppSelect, {
      props: { modelValue: "b", options: OPTIONS },
    })
    const select = wrapper.find("select")
    expect((select.element as HTMLSelectElement).value).toBe("b")
  })

  it("emite update:modelValue ao trocar opção", async () => {
    const wrapper = await mountSuspended(AppSelect, {
      props: { modelValue: "a", options: OPTIONS },
    })
    await wrapper.find("select").setValue("b")
    const emitted = wrapper.emitted("update:modelValue")
    expect(emitted).toBeTruthy()
    expect(emitted![0]).toEqual(["b"])
  })

  it("aplica estilo sm por padrão", async () => {
    const wrapper = await mountSuspended(AppSelect, { props: { options: OPTIONS } })
    const style = wrapper.find("select").attributes("style") || ""
    expect(style).toContain("28px")
  })

  it("aplica estilo md quando size='md'", async () => {
    const wrapper = await mountSuspended(AppSelect, {
      props: { options: OPTIONS, size: "md" },
    })
    const style = wrapper.find("select").attributes("style") || ""
    expect(style).toContain("34px")
  })

  it("desabilita o select quando disabled=true", async () => {
    const wrapper = await mountSuspended(AppSelect, {
      props: { options: OPTIONS, disabled: true },
    })
    expect(wrapper.find("select").attributes("disabled")).toBeDefined()
  })
})
