import { mountSuspended } from "@nuxt/test-utils/runtime"
import { describe, it, expect } from "vitest"
import EditorTransformBuilder from "./EditorTransformBuilder.vue"
import type { TransformDraft } from "~/types/pipeline-editor-v2"
import { OP_TYPES } from "./constants"

function makeDraft(operations: TransformDraft["operations"] = []): TransformDraft {
  return { operations }
}

describe("EditorTransformBuilder", () => {
  it("renders empty state when there are no operations", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: { draft: makeDraft([]) },
    })
    expect(wrapper.text()).toContain("Nenhuma operação ainda")
  })

  it("does NOT render empty state when there are operations", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: { draft: makeDraft([{ op: "drop_column", column: "x" }]) },
    })
    expect(wrapper.text()).not.toContain("Nenhuma operação ainda")
  })

  it("renders an EditorOpCard for each operation", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: {
        draft: makeDraft([
          { op: "drop_column", column: "a" },
          { op: "rename_column", column: "b", newName: "c" },
        ]),
      },
    })
    const cards = wrapper.findAllComponents({ name: "EditorOpCard" })
    expect(cards).toHaveLength(2)
  })

  it("shows 'Adicionar operação' button", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: { draft: makeDraft() },
    })
    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("Adicionar operação"))
    expect(addBtn).toBeDefined()
  })

  it("opens popover with OP_TYPES when 'Adicionar operação' button is clicked", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: { draft: makeDraft() },
    })
    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("Adicionar operação"))
    await addBtn!.trigger("click")

    // Popover should be visible
    const popover = wrapper.find(".op-add-popover")
    expect(popover.exists()).toBe(true)

    // Each OP_TYPE label should appear in the popover
    for (const opType of OP_TYPES) {
      expect(popover.text()).toContain(opType.label)
    }
  })

  it("emits update:draft with new op appended when a type is clicked in popover", async () => {
    const initialOps = [{ op: "drop_column", column: "x" }]
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: { draft: makeDraft(initialOps) },
    })

    // Open the popover
    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("Adicionar operação"))
    await addBtn!.trigger("click")

    // Click "Renomear coluna" (rename_column)
    const renameBtn = wrapper
      .find(".op-add-popover")
      .findAll("button")
      .find((b) => b.text().includes("Renomear coluna"))
    expect(renameBtn).toBeDefined()
    await renameBtn!.trigger("click")

    const emitted = wrapper.emitted("update:draft")
    expect(emitted).toBeTruthy()
    const lastEmit = emitted![emitted!.length - 1][0] as TransformDraft
    expect(lastEmit.operations).toHaveLength(2)
    expect(lastEmit.operations[1].op).toBe("rename_column")
  })

  it("emits markActive when a new op is added", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: { draft: makeDraft() },
    })
    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("Adicionar operação"))
    await addBtn!.trigger("click")

    const firstOpBtn = wrapper.find(".op-add-popover button")
    await firstOpBtn.trigger("click")

    expect(wrapper.emitted("markActive")).toBeTruthy()
  })

  it("emits update:draft without removed op when EditorOpCard emits remove", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: {
        draft: makeDraft([
          { op: "drop_column", column: "a" },
          { op: "rename_column", column: "b", newName: "c" },
        ]),
      },
    })
    const cards = wrapper.findAllComponents({ name: "EditorOpCard" })
    // Remove the first card (index 0)
    await cards[0].vm.$emit("remove", 0)

    const emitted = wrapper.emitted("update:draft")
    expect(emitted).toBeTruthy()
    const lastDraft = emitted![emitted!.length - 1][0] as TransformDraft
    expect(lastDraft.operations).toHaveLength(1)
    expect(lastDraft.operations[0].op).toBe("rename_column")
  })

  it("emits update:draft with swapped ops when EditorOpCard emits move down", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: {
        draft: makeDraft([
          { op: "drop_column", column: "a" },
          { op: "rename_column", column: "b", newName: "c" },
        ]),
      },
    })
    const cards = wrapper.findAllComponents({ name: "EditorOpCard" })
    // Move first card down (dir: 1)
    await cards[0].vm.$emit("move", { index: 0, dir: 1 })

    const emitted = wrapper.emitted("update:draft")
    expect(emitted).toBeTruthy()
    const lastDraft = emitted![emitted!.length - 1][0] as TransformDraft
    expect(lastDraft.operations[0].op).toBe("rename_column")
    expect(lastDraft.operations[1].op).toBe("drop_column")
  })

  it("emits markActive when op is removed", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: {
        draft: makeDraft([{ op: "drop_column", column: "a" }]),
      },
    })
    const cards = wrapper.findAllComponents({ name: "EditorOpCard" })
    await cards[0].vm.$emit("remove", 0)
    expect(wrapper.emitted("markActive")).toBeTruthy()
  })

  it("emits markActive when op is moved", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: {
        draft: makeDraft([
          { op: "drop_column", column: "a" },
          { op: "rename_column", column: "b", newName: "c" },
        ]),
      },
    })
    const cards = wrapper.findAllComponents({ name: "EditorOpCard" })
    await cards[0].vm.$emit("move", { index: 0, dir: 1 })
    expect(wrapper.emitted("markActive")).toBeTruthy()
  })
})
