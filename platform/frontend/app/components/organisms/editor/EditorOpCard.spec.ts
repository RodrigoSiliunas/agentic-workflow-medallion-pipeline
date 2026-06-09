import { mountSuspended } from "@nuxt/test-utils/runtime"
import { describe, it, expect } from "vitest"
import EditorOpCard from "./EditorOpCard.vue"
import type { TransformOperation } from "~/types/pipeline-editor-v2"

// Helper to mount an OpCard with a given op type
async function mountCard(op: TransformOperation, index = 0, total = 3) {
  return mountSuspended(EditorOpCard, {
    props: { op, index, total, tableColumns: [] },
  })
}

describe("EditorOpCard — fieldsFor", () => {
  it("drop_column → 1 field (column)", async () => {
    const wrapper = await mountCard({ op: "drop_column" })
    // The field labels are rendered as uppercase spans
    expect(wrapper.text()).toContain("Coluna")
    // Exactly one field section (no second label)
    expect(wrapper.text()).not.toContain("Para")
    expect(wrapper.text()).not.toContain("Tipo")
  })

  it("rename_column → 2 fields (De, Para)", async () => {
    const wrapper = await mountCard({ op: "rename_column", column: "a", newName: "b" })
    expect(wrapper.text()).toContain("De")
    expect(wrapper.text()).toContain("Para")
  })

  it("cast_column → 2 fields (column, data_type)", async () => {
    const wrapper = await mountCard({ op: "cast_column", column: "a" })
    expect(wrapper.text()).toContain("Coluna")
    expect(wrapper.text()).toContain("Tipo")
  })

  it("regex_replace → 3 fields (column, pattern, replacement)", async () => {
    const wrapper = await mountCard({ op: "regex_replace" })
    expect(wrapper.text()).toContain("Coluna")
    expect(wrapper.text()).toContain("Pattern")
    expect(wrapper.text()).toContain("Substituir")
  })

  it("coalesce → 2 fields (column as new_column, source_columns as multi_columns)", async () => {
    const wrapper = await mountCard({ op: "coalesce" })
    expect(wrapper.text()).toContain("Coluna alvo")
    expect(wrapper.text()).toContain("Fontes")
  })
})

describe("EditorOpCard — emits", () => {
  it("emits change when a field value changes", async () => {
    const wrapper = await mountCard({ op: "rename_column", column: "a", newName: "b" })
    // Trigger change via child component emit
    const columnPickers = wrapper.findAllComponents({ name: "ColumnPicker" })
    if (columnPickers.length > 0) {
      await columnPickers[0].vm.$emit("update:modelValue", "new_col")
      expect(wrapper.emitted("change")).toBeTruthy()
    }
  })

  it("emits remove with index when x-mark icon button is clicked", async () => {
    const wrapper = await mountCard({ op: "drop_column", column: "x" }, 1, 3)
    // Find the remove button (AppIconBtn with icon x-mark)
    const iconBtns = wrapper.findAllComponents({ name: "AppIconBtn" })
    const removeBtn = iconBtns.find((b) => b.props("icon") === "x-mark")
    expect(removeBtn).toBeDefined()
    await removeBtn!.trigger("click")
    const emitted = wrapper.emitted("remove")
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toBe(1)
  })

  it("emits move with { index, dir: -1 } when chevron-up is clicked", async () => {
    // index=1 so chevron-up is not disabled
    const wrapper = await mountCard({ op: "drop_column" }, 1, 3)
    const iconBtns = wrapper.findAllComponents({ name: "AppIconBtn" })
    const upBtn = iconBtns.find((b) => b.props("icon") === "chevron-up")
    expect(upBtn).toBeDefined()
    await upBtn!.trigger("click")
    const emitted = wrapper.emitted("move")
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toEqual({ index: 1, dir: -1 })
  })

  it("emits move with { index, dir: 1 } when chevron-down is clicked", async () => {
    // index=1, total=3 so chevron-down is not disabled
    const wrapper = await mountCard({ op: "drop_column" }, 1, 3)
    const iconBtns = wrapper.findAllComponents({ name: "AppIconBtn" })
    const downBtn = iconBtns.find((b) => b.props("icon") === "chevron-down")
    expect(downBtn).toBeDefined()
    await downBtn!.trigger("click")
    const emitted = wrapper.emitted("move")
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toEqual({ index: 1, dir: 1 })
  })

  it("chevron-up is disabled when index is 0", async () => {
    const wrapper = await mountCard({ op: "drop_column" }, 0, 3)
    const iconBtns = wrapper.findAllComponents({ name: "AppIconBtn" })
    const upBtn = iconBtns.find((b) => b.props("icon") === "chevron-up")
    expect(upBtn!.props("disabled")).toBe(true)
  })

  it("chevron-down is disabled when index is last", async () => {
    const wrapper = await mountCard({ op: "drop_column" }, 2, 3)
    const iconBtns = wrapper.findAllComponents({ name: "AppIconBtn" })
    const downBtn = iconBtns.find((b) => b.props("icon") === "chevron-down")
    expect(downBtn!.props("disabled")).toBe(true)
  })
})
