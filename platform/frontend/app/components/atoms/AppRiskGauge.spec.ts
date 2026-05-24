import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import AppRiskGauge from "./AppRiskGauge.vue"

describe("AppRiskGauge", () => {
  it("displays clamped value 0-10", async () => {
    const wrapper = await mountSuspended(AppRiskGauge, { props: { value: 4 } })
    expect(wrapper.text()).toContain("4")
  })

  it("clamps values above 10", async () => {
    const wrapper = await mountSuspended(AppRiskGauge, { props: { value: 15 } })
    expect(wrapper.text()).toContain("10")
  })

  it("clamps negative values to 0", async () => {
    const wrapper = await mountSuspended(AppRiskGauge, { props: { value: -2 } })
    expect(wrapper.text()).toContain("0")
  })

  it("uses success color for low risk", async () => {
    const wrapper = await mountSuspended(AppRiskGauge, { props: { value: 2 } })
    expect(wrapper.html()).toContain("var(--status-success)")
    expect(wrapper.text()).toContain("baixo")
  })

  it("uses warning color for medium risk", async () => {
    const wrapper = await mountSuspended(AppRiskGauge, { props: { value: 5 } })
    expect(wrapper.html()).toContain("var(--status-warning)")
    expect(wrapper.text()).toContain("medio")
  })

  it("uses error color for high risk", async () => {
    const wrapper = await mountSuspended(AppRiskGauge, { props: { value: 8 } })
    expect(wrapper.html()).toContain("var(--status-error)")
    expect(wrapper.text()).toContain("alto")
  })

  it("sets aria-label with role=img", async () => {
    const wrapper = await mountSuspended(AppRiskGauge, { props: { value: 6 } })
    expect(wrapper.attributes("role")).toBe("img")
    expect(wrapper.attributes("aria-label")).toBe("Risco 6 de 10")
  })
})
