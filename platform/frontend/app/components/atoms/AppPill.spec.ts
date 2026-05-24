import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import AppPill from "./AppPill.vue"

describe("AppPill", () => {
  it("renders slot content", async () => {
    const wrapper = await mountSuspended(AppPill, { slots: { default: "Silver" } })
    expect(wrapper.text()).toContain("Silver")
  })

  it("uses brand tone styles", async () => {
    const wrapper = await mountSuspended(AppPill, {
      props: { tone: "brand" },
      slots: { default: "Brand" },
    })
    const style = wrapper.attributes("style") || ""
    expect(style).toContain("var(--brand-400)")
  })

  it("renders status dot when dot=true", async () => {
    const wrapper = await mountSuspended(AppPill, {
      props: { dot: true, tone: "success" },
      slots: { default: "OK" },
    })
    expect(wrapper.findAll("span").some((s) => (s.attributes("style") || "").includes("var(--status-success)"))).toBe(
      true,
    )
  })

  it("renders icon when icon prop set", async () => {
    const wrapper = await mountSuspended(AppPill, {
      props: { icon: "check" },
      slots: { default: "Done" },
    })
    expect(wrapper.html()).toContain("iconify")
  })

  it("applies xs size class", async () => {
    const wrapper = await mountSuspended(AppPill, {
      props: { size: "xs" },
      slots: { default: "x" },
    })
    expect(wrapper.classes().join(" ")).toContain("text-[10px]")
  })
})
