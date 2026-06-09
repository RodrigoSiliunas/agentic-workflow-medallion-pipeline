import { mountSuspended } from "@nuxt/test-utils/runtime"
import { describe, it, expect } from "vitest"
import EditorModalShell from "./EditorModalShell.vue"

describe("EditorModalShell", () => {
  it("is NOT rendered when open=false", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: false, title: "Test Modal" },
    })
    // The modal backdrop should not be in the DOM
    expect(wrapper.find(".modal-backdrop").exists()).toBe(false)
  })

  it("IS rendered when open=true", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: true, title: "Test Modal" },
    })
    expect(wrapper.find(".modal-backdrop").exists()).toBe(true)
  })

  it("shows the title when open=true", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: true, title: "My Modal Title" },
    })
    expect(wrapper.find("h2.modal-title").text()).toBe("My Modal Title")
  })

  it("shows the icon when icon prop is provided", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: true, title: "Modal With Icon", icon: "sparkles" },
    })
    const iconBox = wrapper.find(".modal-icon-box")
    expect(iconBox.exists()).toBe(true)
    const icon = iconBox.findComponent({ name: "AppIcon" })
    expect(icon.props("name")).toBe("sparkles")
  })

  it("does NOT show icon box when no icon prop is given", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: true, title: "Modal No Icon" },
    })
    expect(wrapper.find(".modal-icon-box").exists()).toBe(false)
  })

  it("emits close when Escape key is pressed and modal is open", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: true, title: "Test Modal" },
    })
    // Dispatch keydown Escape on document
    const event = new KeyboardEvent("keydown", { key: "Escape", bubbles: true })
    document.dispatchEvent(event)
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted("close")).toBeTruthy()
  })

  it("does NOT emit close when Escape is pressed and modal is closed", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: false, title: "Test Modal" },
    })
    const event = new KeyboardEvent("keydown", { key: "Escape", bubbles: true })
    document.dispatchEvent(event)
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted("close")).toBeFalsy()
  })

  it("emits close when backdrop (modal-backdrop) is clicked directly (click.self)", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: true, title: "Test Modal" },
    })
    const backdrop = wrapper.find(".modal-backdrop")
    await backdrop.trigger("click")
    expect(wrapper.emitted("close")).toBeTruthy()
  })

  it("does NOT emit close when clicking inside the modal container (stopPropagation)", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: true, title: "Test Modal" },
    })
    const container = wrapper.find(".modal-container")
    await container.trigger("click")
    // Since click.stop is on the container, click.self on backdrop should not fire
    expect(wrapper.emitted("close")).toBeFalsy()
  })

  it("emits close when close icon button (AppIconBtn x-mark) is clicked", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: true, title: "Test Modal" },
    })
    const closeBtn = wrapper.findComponent({ name: "AppIconBtn" })
    expect(closeBtn.exists()).toBe(true)
    await closeBtn.trigger("click")
    expect(wrapper.emitted("close")).toBeTruthy()
  })

  it("renders slot content in modal-body", async () => {
    const wrapper = await mountSuspended(EditorModalShell, {
      props: { open: true, title: "Test Modal" },
      slots: { default: "<p class='slot-content'>Hello Slot</p>" },
    })
    expect(wrapper.find(".modal-body .slot-content").exists()).toBe(true)
    expect(wrapper.find(".modal-body .slot-content").text()).toBe("Hello Slot")
  })
})
