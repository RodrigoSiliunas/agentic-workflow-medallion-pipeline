import { describe, it, expect, vi } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import { defineComponent, nextTick, ref } from "vue"

// Mock do useLocalStorage para isolar os testes do localStorage real
vi.mock("@vueuse/core", async (importOriginal) => {
  const original = await importOriginal<typeof import("@vueuse/core")>()
  return {
    ...original,
    useLocalStorage: (_key: string, defaults: unknown) => ref(structuredClone(defaults)),
  }
})

const TestComponent = defineComponent({
  setup() {
    const { settings, reset } = useEditorSettings()
    return { settings, reset }
  },
  template: `<div :data-layout="settings.layout" />`,
})

describe("useEditorSettings", () => {
  it("retorna defaults: layout=tri_pane, density=comfortable, rails e timeline ativos", async () => {
    const wrapper = await mountSuspended(TestComponent)
    const vm = wrapper.vm as { settings: Record<string, unknown>; reset: () => void }
    expect(vm.settings.layout).toBe("tri_pane")
    expect(vm.settings.showStateTimeline).toBe(true)
    expect(vm.settings.density).toBe("comfortable")
    expect(vm.settings.showSessionsRail).toBe(true)
  })

  it("permite alterar o layout", async () => {
    const wrapper = await mountSuspended(TestComponent)
    const vm = wrapper.vm as { settings: Record<string, unknown>; reset: () => void }
    vm.settings.layout = "chat_dominant"
    await nextTick()
    expect(vm.settings.layout).toBe("chat_dominant")
  })

  it("reset restaura os defaults", async () => {
    const wrapper = await mountSuspended(TestComponent)
    const vm = wrapper.vm as { settings: Record<string, unknown>; reset: () => void }
    vm.settings.layout = "wizard"
    await nextTick()
    expect(vm.settings.layout).toBe("wizard")
    vm.reset()
    await nextTick()
    expect(vm.settings.layout).toBe("tri_pane")
  })

  it("data-layout no template reflete o layout corrente", async () => {
    const wrapper = await mountSuspended(TestComponent)
    expect(wrapper.attributes("data-layout")).toBe("tri_pane")
  })
})
