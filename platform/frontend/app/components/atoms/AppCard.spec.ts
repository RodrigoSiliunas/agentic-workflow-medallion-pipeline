import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import AppCard from "./AppCard.vue"

describe("AppCard", () => {
  it("renders slot inside default div", async () => {
    const wrapper = await mountSuspended(AppCard, {
      slots: { default: "Hello" },
    })
    expect(wrapper.element.tagName).toBe("DIV")
    expect(wrapper.text()).toBe("Hello")
  })

  it("applies inner-glow shadow when glow=true", async () => {
    const wrapper = await mountSuspended(AppCard, {
      props: { glow: true },
    })
    expect((wrapper.attributes("style") || "")).toContain("var(--shadow-inner-glow)")
  })

  it("applies interactive classes", async () => {
    const wrapper = await mountSuspended(AppCard, {
      props: { interactive: true },
    })
    const classes = wrapper.classes().join(" ")
    expect(classes).toContain("cursor-pointer")
  })

  it("respects padding none", async () => {
    const wrapper = await mountSuspended(AppCard, {
      props: { padding: "none" },
    })
    const classes = wrapper.classes().join(" ")
    expect(classes).not.toMatch(/\bp-\d/)
  })

  it("renders as different tag when tag prop set", async () => {
    const wrapper = await mountSuspended(AppCard, {
      props: { tag: "article" },
    })
    expect(wrapper.element.tagName).toBe("ARTICLE")
  })
})
