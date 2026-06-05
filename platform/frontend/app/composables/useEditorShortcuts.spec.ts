import { describe, it, expect, vi, afterEach } from "vitest"
import { defineComponent, nextTick } from "vue"
import { mountSuspended } from "@nuxt/test-utils/runtime"

function fireKey(opts: Partial<KeyboardEventInit>) {
  window.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, ...opts }))
}

describe("useEditorShortcuts", () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it("Ctrl+Enter chama onSend", async () => {
    const onSend = vi.fn()
    const TestComp = defineComponent({
      setup() { useEditorShortcuts({ onSend }) },
      template: `<div />`,
    })
    await mountSuspended(TestComp)
    fireKey({ key: "Enter", ctrlKey: true })
    await nextTick()
    expect(onSend).toHaveBeenCalledTimes(1)
  })

  it("Escape chama onEscape", async () => {
    const onEscape = vi.fn()
    const TestComp = defineComponent({
      setup() { useEditorShortcuts({ onEscape }) },
      template: `<div />`,
    })
    await mountSuspended(TestComp)
    fireKey({ key: "Escape" })
    await nextTick()
    expect(onEscape).toHaveBeenCalledTimes(1)
  })

  it("Ctrl+S chama onSaveDraft", async () => {
    const onSaveDraft = vi.fn()
    const TestComp = defineComponent({
      setup() { useEditorShortcuts({ onSaveDraft }) },
      template: `<div />`,
    })
    await mountSuspended(TestComp)
    fireKey({ key: "s", ctrlKey: true })
    await nextTick()
    expect(onSaveDraft).toHaveBeenCalledTimes(1)
  })

  it("Ctrl+P chama onRunPreview", async () => {
    const onRunPreview = vi.fn()
    const TestComp = defineComponent({
      setup() { useEditorShortcuts({ onRunPreview }) },
      template: `<div />`,
    })
    await mountSuspended(TestComp)
    fireKey({ key: "p", ctrlKey: true })
    await nextTick()
    expect(onRunPreview).toHaveBeenCalledTimes(1)
  })

  it("Ctrl+N chama onNewSession", async () => {
    const onNewSession = vi.fn()
    const TestComp = defineComponent({
      setup() { useEditorShortcuts({ onNewSession }) },
      template: `<div />`,
    })
    await mountSuspended(TestComp)
    fireKey({ key: "n", ctrlKey: true })
    await nextTick()
    expect(onNewSession).toHaveBeenCalledTimes(1)
  })

  it("Ctrl+K chama onShare", async () => {
    const onShare = vi.fn()
    const TestComp = defineComponent({
      setup() { useEditorShortcuts({ onShare }) },
      template: `<div />`,
    })
    await mountSuspended(TestComp)
    fireKey({ key: "k", ctrlKey: true })
    await nextTick()
    expect(onShare).toHaveBeenCalledTimes(1)
  })

  it("? chama onHelp quando foco não é input/textarea", async () => {
    const onHelp = vi.fn()
    const TestComp = defineComponent({
      setup() { useEditorShortcuts({ onHelp }) },
      template: `<div tabindex="0" id="editor-root" />`,
    })
    const wrapper = await mountSuspended(TestComp)
    // Foca o div (não é input nem textarea)
    const div = wrapper.find("#editor-root").element as HTMLElement
    div.focus()
    fireKey({ key: "?" })
    await nextTick()
    expect(onHelp).toHaveBeenCalledTimes(1)
  })

  it("? com Ctrl NÃO chama onHelp", async () => {
    const onHelp = vi.fn()
    const TestComp = defineComponent({
      setup() { useEditorShortcuts({ onHelp }) },
      template: `<div />`,
    })
    await mountSuspended(TestComp)
    fireKey({ key: "?", ctrlKey: true })
    await nextTick()
    expect(onHelp).not.toHaveBeenCalled()
  })
})
