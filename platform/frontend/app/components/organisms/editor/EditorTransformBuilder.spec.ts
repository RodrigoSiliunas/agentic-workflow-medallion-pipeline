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

  // O menu agora é TELEPORTADO pro body (fix do clipping pela tab bar) —
  // os testes consultam document.body em vez do wrapper.
  function bodyMenu(): HTMLElement | null {
    return document.body.querySelector('[data-testid="add-op-menu"]')
  }

  it("opens teleported popover with OP_TYPES when 'Adicionar operação' is clicked", async () => {
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: { draft: makeDraft() },
    })
    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("Adicionar operação"))
    await addBtn!.trigger("click")
    await nextTick()

    const menu = bodyMenu()
    expect(menu).not.toBeNull()
    for (const opType of OP_TYPES) {
      expect(menu!.textContent).toContain(opType.label)
    }
    await addBtn!.trigger("click") // fecha (higiene entre testes)
  })

  it("emits update:draft with new op appended when a type is clicked in popover", async () => {
    const initialOps = [{ op: "drop_column", column: "x" }]
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: { draft: makeDraft(initialOps) },
    })

    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("Adicionar operação"))
    await addBtn!.trigger("click")
    await nextTick()

    const renameBtn = [...bodyMenu()!.querySelectorAll("button")].find((b) =>
      b.textContent?.includes("Renomear coluna"),
    ) as HTMLElement
    expect(renameBtn).toBeDefined()
    renameBtn.click()
    await nextTick()

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
    await nextTick()

    const firstOpBtn = bodyMenu()!.querySelector("button") as HTMLElement
    firstOpBtn.click()
    await nextTick()

    expect(wrapper.emitted("markActive")).toBeTruthy()
  })

  it("renders node selector with locked Bronze/Gold and emits selectNode on silver pick", async () => {
    const nodes = [
      {
        id: "silver_dedup", layer: "silver" as const, taskKey: "silver_dedup",
        filePath: "x", inputTables: [], outputTables: ["cat.silver.messages_clean"],
        supportedOperations: [], insertionMarker: "#",
      },
      {
        id: "silver_entities", layer: "silver" as const, taskKey: "silver_entities",
        filePath: "y", inputTables: [], outputTables: ["cat.silver.leads"],
        supportedOperations: [], insertionMarker: "#",
      },
    ]
    const wrapper = await mountSuspended(EditorTransformBuilder, {
      props: { draft: makeDraft(), nodes, selectedNodeId: "silver_dedup" },
    })

    // Botão do seletor mostra a tabela do node ativo
    const selBtn = wrapper.find('[data-testid="node-selector"]')
    expect(selBtn.exists()).toBe(true)
    expect(selBtn.text()).toContain("cat.silver.messages_clean")

    await selBtn.trigger("click")
    await nextTick()

    const menu = document.body.querySelector('[data-testid="node-selector-menu"]')
    expect(menu).not.toBeNull()
    // Camadas bloqueadas visíveis
    expect(menu!.textContent).toContain("Bronze · bloqueada")
    expect(menu!.textContent).toContain("Gold · bloqueada")

    // Escolher o outro node silver emite selectNode
    const opt = menu!.querySelector('[data-testid="node-option-silver_entities"]') as HTMLElement
    opt.click()
    await nextTick()
    expect(wrapper.emitted("selectNode")?.[0]).toEqual(["silver_entities"])
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
