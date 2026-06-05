import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import SchemaColumnRow from "./SchemaColumnRow.vue"
import type { SchemaColumn } from "~/types/pipeline-editor-v2"

describe("SchemaColumnRow", () => {
  it("renderiza nome e tipo da coluna", async () => {
    const column: SchemaColumn = { name: "customer_id", type: "string" }
    const wrapper = await mountSuspended(SchemaColumnRow, { props: { column } })
    expect(wrapper.text()).toContain("customer_id")
    expect(wrapper.text()).toContain("string")
  })

  it("exibe NOT NULL quando nullable=false", async () => {
    const column: SchemaColumn = { name: "id", type: "bigint", nullable: false }
    const wrapper = await mountSuspended(SchemaColumnRow, { props: { column } })
    expect(wrapper.text()).toContain("NOT NULL")
  })

  it("exibe label 'Removida' quando state=removed", async () => {
    const column: SchemaColumn = { name: "ssn", type: "string", state: "removed" }
    const wrapper = await mountSuspended(SchemaColumnRow, { props: { column } })
    expect(wrapper.text()).toContain("Removida")
  })

  it("exibe nome anterior quando state=renamed", async () => {
    const column: SchemaColumn = {
      name: "customer_id",
      type: "string",
      state: "renamed",
      from: "cliente_id",
    }
    const wrapper = await mountSuspended(SchemaColumnRow, { props: { column } })
    expect(wrapper.text()).toContain("cliente_id")
    expect(wrapper.text()).toContain("customer_id")
  })

  it("exibe label 'Sem mudança' para colunas sem estado", async () => {
    const column: SchemaColumn = { name: "email", type: "string" }
    const wrapper = await mountSuspended(SchemaColumnRow, { props: { column } })
    expect(wrapper.text()).toContain("Sem mudança")
  })

  it("exibe nota quando fornecida", async () => {
    const column: SchemaColumn = { name: "col", type: "string", note: "info extra" }
    const wrapper = await mountSuspended(SchemaColumnRow, { props: { column } })
    expect(wrapper.text()).toContain("info extra")
  })
})
