import { mountSuspended } from "@nuxt/test-utils/runtime"
import { describe, it, expect } from "vitest"
import EditorStateTimeline from "./EditorStateTimeline.vue"

const STATE_LABELS = [
  "Aguardando",
  "Gerando proposta",
  "Preview",
  "Validando",
  "Abrindo PR",
  "PR criado",
]

describe("EditorStateTimeline", () => {
  it("renders all 6 step labels", async () => {
    const wrapper = await mountSuspended(EditorStateTimeline, {
      props: { current: "idle", error: null, durationMs: null },
    })
    const text = wrapper.text()
    for (const label of STATE_LABELS) {
      expect(text).toContain(label)
    }
  })

  it("applies brand styling (step--current class) to the current state", async () => {
    const wrapper = await mountSuspended(EditorStateTimeline, {
      props: { current: "running_preview", error: null, durationMs: null },
    })
    const steps = wrapper.findAll(".step")
    // "running_preview" is index 2
    expect(steps[2].classes()).toContain("step--current")
  })

  it("applies past styling to states before the current one", async () => {
    const wrapper = await mountSuspended(EditorStateTimeline, {
      props: { current: "validating", error: null, durationMs: null },
    })
    const steps = wrapper.findAll(".step")
    // "validating" is index 3 — steps 0,1,2 should be past
    expect(steps[0].classes()).toContain("step--past")
    expect(steps[1].classes()).toContain("step--past")
    expect(steps[2].classes()).toContain("step--past")
  })

  it("applies future styling to states after the current one", async () => {
    const wrapper = await mountSuspended(EditorStateTimeline, {
      props: { current: "generating_proposal", error: null, durationMs: null },
    })
    const steps = wrapper.findAll(".step")
    // "generating_proposal" is index 1 — steps 2..5 should be future
    expect(steps[2].classes()).toContain("step--future")
    expect(steps[5].classes()).toContain("step--future")
  })

  it("shows error block with exclamation icon and retry button when error is set on a non-terminal state", async () => {
    const wrapper = await mountSuspended(EditorStateTimeline, {
      props: { current: "running_preview", error: "Something went wrong", durationMs: null },
    })
    // Error block should appear
    const errorBlock = wrapper.find(".timeline-error")
    expect(errorBlock.exists()).toBe(true)
    expect(errorBlock.text()).toContain("Something went wrong")

    // Retry button
    const retryBtn = errorBlock.find("button")
    expect(retryBtn.exists()).toBe(true)
    expect(retryBtn.text()).toContain("Tentar novamente")
  })

  it("applies step--errored class to current step when error is present", async () => {
    const wrapper = await mountSuspended(EditorStateTimeline, {
      props: { current: "validating", error: "Validation failed", durationMs: null },
    })
    const steps = wrapper.findAll(".step")
    // "validating" is index 3
    expect(steps[3].classes()).toContain("step--errored")
  })

  it("emits retry when retry button is clicked", async () => {
    const wrapper = await mountSuspended(EditorStateTimeline, {
      props: { current: "opening_pr", error: "PR failed", durationMs: null },
    })
    const retryBtn = wrapper.find(".timeline-error button")
    await retryBtn.trigger("click")
    expect(wrapper.emitted("retry")).toBeTruthy()
  })

  it("does NOT show error block when error is null", async () => {
    const wrapper = await mountSuspended(EditorStateTimeline, {
      props: { current: "generating_proposal", error: null, durationMs: null },
    })
    expect(wrapper.find(".timeline-error").exists()).toBe(false)
  })

  it("does NOT show error block when state is idle even with error string", async () => {
    const wrapper = await mountSuspended(EditorStateTimeline, {
      props: { current: "idle", error: "stale error", durationMs: null },
    })
    expect(wrapper.find(".timeline-error").exists()).toBe(false)
  })

  it("applies pr_created styling to last step when current is pr_created", async () => {
    const wrapper = await mountSuspended(EditorStateTimeline, {
      props: { current: "pr_created", error: null, durationMs: null },
    })
    const steps = wrapper.findAll(".step")
    expect(steps[5].classes()).toContain("step--pr_created")
  })
})
