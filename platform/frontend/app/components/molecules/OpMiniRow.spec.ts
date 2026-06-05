import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import OpMiniRow from "./OpMiniRow.vue"
import type { TransformOperation } from "~/types/pipeline-editor"

describe("OpMiniRow", () => {
  it("renderiza o índice + 1", async () => {
    const op: TransformOperation = { op: "trim", column: "email" }
    const wrapper = await mountSuspended(OpMiniRow, { props: { op, index: 0 } })
    expect(wrapper.text()).toContain("1")
  })

  it("renderiza o nome da operação", async () => {
    const op: TransformOperation = { op: "mask_pii", column: "ssn" }
    const wrapper = await mountSuspended(OpMiniRow, { props: { op, index: 2 } })
    expect(wrapper.text()).toContain("mask_pii")
  })

  it("exibe colunas de/para em rename_column", async () => {
    const op: TransformOperation = { op: "rename_column", column: "cliente_id", newName: "customer_id" }
    const wrapper = await mountSuspended(OpMiniRow, { props: { op, index: 0 } })
    expect(wrapper.text()).toContain("cliente_id")
    expect(wrapper.text()).toContain("customer_id")
    expect(wrapper.text()).toContain("→")
  })

  it("exibe expressão em derive_column", async () => {
    const op: TransformOperation = { op: "derive_column", column: "total", expression: "qty * price" }
    const wrapper = await mountSuspended(OpMiniRow, { props: { op, index: 0 } })
    expect(wrapper.text()).toContain("total")
    expect(wrapper.text()).toContain("qty * price")
  })

  it("exibe tipo em cast_column", async () => {
    const op: TransformOperation = { op: "cast_column", column: "age", dataType: "int" }
    const wrapper = await mountSuspended(OpMiniRow, { props: { op, index: 0 } })
    expect(wrapper.text()).toContain("age")
    expect(wrapper.text()).toContain("int")
  })
})
