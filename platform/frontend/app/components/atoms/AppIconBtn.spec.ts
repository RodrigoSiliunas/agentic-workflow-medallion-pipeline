import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import AppIconBtn from "./AppIconBtn.vue"

describe("AppIconBtn", () => {
  it("renders button with aria-label", async () => {
    const wrapper = await mountSuspended(AppIconBtn, {
      props: { icon: "plus", label: "Adicionar operacao" },
    })
    expect(wrapper.element.tagName).toBe("BUTTON")
    expect(wrapper.attributes("aria-label")).toBe("Adicionar operacao")
  })

  it("renders icon via AppIcon child", async () => {
    const wrapper = await mountSuspended(AppIconBtn, {
      props: { icon: "trash", label: "Remover" },
    })
    expect(wrapper.html()).toContain("iconify")
  })

  it("sets aria-pressed when active", async () => {
    const wrapper = await mountSuspended(AppIconBtn, {
      props: { icon: "x", label: "Fechar", active: true },
    })
    expect(wrapper.attributes("aria-pressed")).toBe("true")
  })

  it("does not set aria-pressed when inactive", async () => {
    const wrapper = await mountSuspended(AppIconBtn, {
      props: { icon: "x", label: "Fechar" },
    })
    expect(wrapper.attributes("aria-pressed")).toBeUndefined()
  })

  it("size 24 applies w-6 h-6", async () => {
    const wrapper = await mountSuspended(AppIconBtn, {
      props: { icon: "x", label: "x", size: 24 },
    })
    expect(wrapper.classes().join(" ")).toContain("w-6 h-6")
  })

  it("size 32 applies w-8 h-8", async () => {
    const wrapper = await mountSuspended(AppIconBtn, {
      props: { icon: "x", label: "x", size: 32 },
    })
    expect(wrapper.classes().join(" ")).toContain("w-8 h-8")
  })

  it("disabled attribute set", async () => {
    const wrapper = await mountSuspended(AppIconBtn, {
      props: { icon: "x", label: "x", disabled: true },
    })
    expect(wrapper.attributes("disabled")).toBeDefined()
  })
})
