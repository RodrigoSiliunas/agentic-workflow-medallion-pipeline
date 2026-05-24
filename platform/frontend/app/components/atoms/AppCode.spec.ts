import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import AppCode from "./AppCode.vue"

describe("AppCode", () => {
  it("renders slot in code element", async () => {
    const wrapper = await mountSuspended(AppCode, {
      slots: { default: "silver_dedup" },
    })
    expect(wrapper.element.tagName).toBe("CODE")
    expect(wrapper.text()).toBe("silver_dedup")
  })

  it("default variant uses surface-elevated", async () => {
    const wrapper = await mountSuspended(AppCode, { slots: { default: "x" } })
    expect((wrapper.attributes("style") || "")).toContain("var(--surface-elevated)")
  })

  it("brand variant uses brand-400", async () => {
    const wrapper = await mountSuspended(AppCode, {
      props: { variant: "brand" },
      slots: { default: "x" },
    })
    expect((wrapper.attributes("style") || "")).toContain("var(--brand-400)")
  })
})
