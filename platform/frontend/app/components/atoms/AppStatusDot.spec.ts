import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import AppStatusDot from "./AppStatusDot.vue"

describe("AppStatusDot", () => {
  it("renders with default neutral tone", async () => {
    const wrapper = await mountSuspended(AppStatusDot)
    expect((wrapper.attributes("style") || "")).toContain("var(--text-tertiary)")
  })

  it("applies success tone color", async () => {
    const wrapper = await mountSuspended(AppStatusDot, { props: { tone: "success" } })
    expect((wrapper.attributes("style") || "")).toContain("var(--status-success)")
  })

  it("renders pulse ring when pulse=true", async () => {
    const wrapper = await mountSuspended(AppStatusDot, { props: { pulse: true } })
    expect(wrapper.classes()).toContain("status-pulse")
    expect(wrapper.find(".ping-ring").exists()).toBe(true)
  })

  it("uses custom size", async () => {
    const wrapper = await mountSuspended(AppStatusDot, { props: { size: 10 } })
    expect((wrapper.attributes("style") || "")).toContain("width: 10px")
  })

  it("attaches ariaLabel and role", async () => {
    const wrapper = await mountSuspended(AppStatusDot, {
      props: { ariaLabel: "PR aberto" },
    })
    expect(wrapper.attributes("aria-label")).toBe("PR aberto")
    expect(wrapper.attributes("role")).toBe("status")
  })
})
