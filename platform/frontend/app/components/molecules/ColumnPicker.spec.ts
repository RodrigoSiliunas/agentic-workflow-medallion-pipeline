import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import ColumnPicker from "./ColumnPicker.vue"
import type { SchemaColumn } from "~/types/pipeline-editor-v2"

const COLUMNS: SchemaColumn[] = [
  { name: "customer_id", type: "string" },
  { name: "ssn", type: "string", pii: true },
  { name: "created_at", type: "timestamp" },
]

describe("ColumnPicker", () => {
  it("renderiza o placeholder quando sem valor", async () => {
    const wrapper = await mountSuspended(ColumnPicker, {
      props: { columns: COLUMNS, placeholder: "Selecione coluna…" },
    })
    expect(wrapper.text()).toContain("Selecione coluna…")
  })

  it("mostra o valor selecionado no trigger", async () => {
    const wrapper = await mountSuspended(ColumnPicker, {
      props: { modelValue: "customer_id", columns: COLUMNS },
    })
    expect(wrapper.text()).toContain("customer_id")
  })

  it("abre dropdown ao clicar no trigger", async () => {
    const wrapper = await mountSuspended(ColumnPicker, { props: { columns: COLUMNS } })
    await wrapper.find("button").trigger("click")
    expect(document.body.innerHTML).toContain("customer_id")
    expect(document.body.innerHTML).toContain("ssn")
  })

  it("exibe badge PII para colunas marcadas", async () => {
    const wrapper = await mountSuspended(ColumnPicker, { props: { columns: COLUMNS } })
    await wrapper.find("button").trigger("click")
    expect(document.body.innerHTML).toContain("PII")
  })

  it("emite update:modelValue ao chamar pick", async () => {
    const wrapper = await mountSuspended(ColumnPicker, { props: { columns: COLUMNS } })
    // Usa método exposto para simular seleção de coluna
    type Exposed = { pick: (name: string) => void }
    ;(wrapper.vm as unknown as Exposed).pick("customer_id")
    const emitted = wrapper.emitted("update:modelValue")
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toBe("customer_id")
  })
})
