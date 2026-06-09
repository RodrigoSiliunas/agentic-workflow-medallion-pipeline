import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { defineComponent, nextTick } from "vue"
import { mountSuspended } from "@nuxt/test-utils/runtime"

describe("useMockDictation", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("começa com listening=false", async () => {
    const transcripts: string[] = []
    const TestComp = defineComponent({
      setup() {
        const { listening } = useMockDictation((t) => transcripts.push(t))
        return { listening }
      },
      template: `<div :data-listening="String(listening)" />`,
    })
    const wrapper = await mountSuspended(TestComp)
    // refs são auto-unwrapped no template; data-listening reflete o valor boolean
    expect(wrapper.attributes("data-listening")).toBe("false")
  })

  it("toggle inicia a escuta e emite transcript após ~2.4s", async () => {
    const transcripts: string[] = []
    const TestComp = defineComponent({
      setup() {
        const { listening, toggle } = useMockDictation((t) => transcripts.push(t))
        // expõe como ref diretamente p/ acesso nos testes via composable retornado
        return { dictation: { listening, toggle } }
      },
      template: `<div />`,
    })
    const wrapper = await mountSuspended(TestComp)
    // refs retornados como objeto aninhado mantêm o tipo Ref
    const vm = wrapper.vm as { dictation: ReturnType<typeof useMockDictation> }

    // Inicia escuta
    vm.dictation.toggle()
    await nextTick()
    expect(vm.dictation.listening.value).toBe(true)

    // Antes dos 2.4s: sem transcript
    vi.advanceTimersByTime(2000)
    await nextTick()
    expect(transcripts).toHaveLength(0)
    expect(vm.dictation.listening.value).toBe(true)

    // Após 2.4s: transcript emitido, listening=false
    vi.advanceTimersByTime(500)
    await nextTick()
    expect(transcripts).toHaveLength(1)
    expect(transcripts[0]).toBeTruthy()
    expect(vm.dictation.listening.value).toBe(false)
  })

  it("stop cancela o timer e não emite transcript", async () => {
    const transcripts: string[] = []
    const TestComp = defineComponent({
      setup() {
        const { listening, start, stop } = useMockDictation((t) => transcripts.push(t))
        return { dictation: { listening, start, stop } }
      },
      template: `<div />`,
    })
    const wrapper = await mountSuspended(TestComp)
    const vm = wrapper.vm as { dictation: ReturnType<typeof useMockDictation> }

    vm.dictation.start()
    await nextTick()
    vi.advanceTimersByTime(1000)
    vm.dictation.stop()
    await nextTick()
    vi.advanceTimersByTime(2000)
    await nextTick()
    expect(transcripts).toHaveLength(0)
    expect(vm.dictation.listening.value).toBe(false)
  })
})
