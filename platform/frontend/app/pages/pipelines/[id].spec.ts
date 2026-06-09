/**
 * Smoke test da página pipelines/[id].vue em mock mode.
 * Verifica: aba padrão = edit e PipelineEditorV2 monta.
 */
import { describe, it, expect, vi } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import PipelineIdPage from "./[id].vue"

const mockWorkspace = {
  id: "test_pip",
  name: "Test Pipeline",
  description: null,
  databricksJobId: null,
  githubRepo: null,
  config: {},
  manifest: { templateSlug: "test", displayName: "Test", nodes: [] },
}

// Mock do Pinia store — retorna valores diretos (Pinia auto-unwraps refs)
vi.mock("~/stores/pipelines", () => ({
  usePipelinesStore: () => ({
    workspace: mockWorkspace,
    editSessions: [],
    activeEditSessionId: "",
    activeDraft: null,
    preview: null,
    loaded: true,
    load: vi.fn().mockResolvedValue(undefined),
    loadWorkspace: vi.fn().mockResolvedValue(undefined),
    setActiveEditSession: vi.fn(),
  }),
}))

vi.mock("~/composables/usePipelinesApi", () => ({
  usePipelinesApi: () => ({ exportPreview: vi.fn() }),
}))

// Stubs globais para componentes pesados
const stubs = {
  PipelineEditorV2: { template: `<div data-testid="pipeline-editor-v2" />` },
  DataPreviewGrid: { template: `<div data-testid="data-preview-grid" />` },
  PipelineDiagram: { template: `<div data-testid="pipeline-diagram" />` },
  EditorHistoryView: { template: `<div data-testid="editor-history-view" />` },
  MetricCard: { template: `<div />` },
  AppButton: { template: `<button><slot /></button>` },
  EmptyState: { template: `<div data-testid="empty-state" />` },
}

describe("pipelines/[id].vue — smoke test", () => {
  it("aba padrão é 'edit' — editor monta full-bleed e a barra de abas da página fica oculta", async () => {
    const wrapper = await mountSuspended(PipelineIdPage, {
      route: "/pipelines/test_pip",
      global: { stubs },
    })
    // Editor montado por padrão...
    expect(wrapper.find("[data-testid='pipeline-editor-v2']").exists()).toBe(true)
    // ...e o header da página (back + abas) é ocultado na aba Editor (full-bleed).
    const editorTab = wrapper.findAll("button").find((b) => b.text().includes("Editor"))
    expect(editorTab).toBeUndefined()
  })

  it("PipelineEditorV2 monta quando aba=edit", async () => {
    const wrapper = await mountSuspended(PipelineIdPage, {
      route: "/pipelines/test_pip",
      global: { stubs },
    })
    expect(wrapper.find("[data-testid='pipeline-editor-v2']").exists()).toBe(true)
  })

  it("a barra de abas da página aparece nas abas não-edit (navegação entre abas)", async () => {
    const wrapper = await mountSuspended(PipelineIdPage, {
      route: "/pipelines/test_pip",
      global: { stubs },
    })
    // Sai do editor via o método exposto changeTab.
    ;(wrapper.vm as unknown as { changeTab: (t: string) => void }).changeTab("overview")
    await wrapper.vm.$nextTick()

    expect(wrapper.find("[data-testid='pipeline-editor-v2']").exists()).toBe(false)
    // Agora a barra de abas está visível para navegação.
    const tabLabels = wrapper.findAll("button").map((b) => b.text())
    expect(tabLabels.some((t) => t.includes("Editor"))).toBe(true)
    expect(tabLabels.some((t) => t.includes("Histórico"))).toBe(true)
  })

  it("EditorHistoryView aparece ao selecionar a aba Histórico", async () => {
    const wrapper = await mountSuspended(PipelineIdPage, {
      route: "/pipelines/test_pip",
      global: { stubs },
    })
    ;(wrapper.vm as unknown as { changeTab: (t: string) => void }).changeTab("history")
    await wrapper.vm.$nextTick()
    expect(wrapper.find("[data-testid='editor-history-view']").exists()).toBe(true)
  })
})
