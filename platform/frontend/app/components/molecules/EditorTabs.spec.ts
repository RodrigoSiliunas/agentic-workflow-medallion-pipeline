import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import EditorTabs from "./EditorTabs.vue"

const TABS = [
  { id: "rascunho", label: "Rascunho", icon: "pencil-square", count: 3 },
  { id: "preview", label: "Preview", icon: "play" },
  { id: "pr", label: "PR", icon: "code-bracket" },
]

describe("EditorTabs", () => {
  it("renderiza todos os tabs", async () => {
    const wrapper = await mountSuspended(EditorTabs, {
      props: { tabs: TABS, modelValue: "rascunho" },
    })
    expect(wrapper.text()).toContain("Rascunho")
    expect(wrapper.text()).toContain("Preview")
    expect(wrapper.text()).toContain("PR")
  })

  it("aplica classe ativa ao tab selecionado", async () => {
    const wrapper = await mountSuspended(EditorTabs, {
      props: { tabs: TABS, modelValue: "preview" },
    })
    const buttons = wrapper.findAll("button")
    const previewBtn = buttons.find((b) => b.text().includes("Preview"))
    expect(previewBtn?.classes().join(" ")).toContain("bg-[var(--surface)]")
  })

  it("mostra badge de contagem quando count definido", async () => {
    const wrapper = await mountSuspended(EditorTabs, {
      props: { tabs: TABS, modelValue: "rascunho" },
    })
    expect(wrapper.text()).toContain("3")
  })

  it("emite update:modelValue ao clicar", async () => {
    const wrapper = await mountSuspended(EditorTabs, {
      props: { tabs: TABS, modelValue: "rascunho" },
    })
    const buttons = wrapper.findAll("button")
    const previewBtn = buttons.find((b) => b.text().includes("Preview"))!
    await previewBtn.trigger("click")
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual(["preview"])
  })

  it("usa role=tablist e aria-selected", async () => {
    const wrapper = await mountSuspended(EditorTabs, {
      props: { tabs: TABS, modelValue: "pr" },
    })
    expect(wrapper.attributes("role")).toBe("tablist")
    const prBtn = wrapper.findAll("button").find((b) => b.text().includes("PR"))!
    expect(prBtn.attributes("aria-selected")).toBe("true")
  })
})
