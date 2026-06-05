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
  it("aba padrão é 'edit' ao abrir", async () => {
    const wrapper = await mountSuspended(PipelineIdPage, {
      route: "/pipelines/test_pip",
      global: { stubs },
    })
    const tabs = wrapper.findAll("button")
    const editorTab = tabs.find((b) => b.text().includes("Editor"))
    expect(editorTab).toBeDefined()
    const style = editorTab!.attributes("style") || ""
    expect(style).toContain("var(--brand-600)")
  })

  it("PipelineEditorV2 monta quando aba=edit", async () => {
    const wrapper = await mountSuspended(PipelineIdPage, {
      route: "/pipelines/test_pip",
      global: { stubs },
    })
    expect(wrapper.find("[data-testid='pipeline-editor-v2']").exists()).toBe(true)
  })

  it("PipelineEditorV2 desmonta ao trocar para aba overview", async () => {
    const wrapper = await mountSuspended(PipelineIdPage, {
      route: "/pipelines/test_pip",
      global: { stubs },
    })
    const overviewTab = wrapper.findAll("button").find((b) => b.text().includes("Overview"))
    await overviewTab!.trigger("click")
    expect(wrapper.find("[data-testid='pipeline-editor-v2']").exists()).toBe(false)
  })

  it("EditorHistoryView aparece ao clicar em Histórico", async () => {
    const wrapper = await mountSuspended(PipelineIdPage, {
      route: "/pipelines/test_pip",
      global: { stubs },
    })
    const historyTab = wrapper.findAll("button").find((b) => b.text().includes("Histórico"))
    await historyTab!.trigger("click")
    expect(wrapper.find("[data-testid='editor-history-view']").exists()).toBe(true)
  })
})
