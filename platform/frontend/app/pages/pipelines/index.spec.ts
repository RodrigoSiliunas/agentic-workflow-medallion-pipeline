import { describe, it, expect, vi } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import PipelinesIndexPage from "./index.vue"

const mockPipelines = [
  {
    id: "pip_1",
    name: "WhatsApp Seguradora",
    status: "SUCCESS" as const,
    lastRunAt: new Date(Date.now() - 3600000).toISOString(),
    nextRunAt: null,
    threadCount: 153000,
  },
  {
    id: "pip_2",
    name: "CRM Pipeline",
    status: "IDLE" as const,
    lastRunAt: null,
    nextRunAt: null,
    threadCount: 0,
  },
]

const mockStoreFn = vi.fn(() => ({
  pipelines: mockPipelines,
  loaded: true,
  load: vi.fn().mockResolvedValue(undefined),
}))

vi.mock("~/stores/pipelines", () => ({
  usePipelinesStore: () => mockStoreFn(),
}))

const stubs = {
  PipelineCard: { template: `<div data-testid="pipeline-card" @click="$emit('select', 'pip_1')" />` },
  EmptyState: { template: `<div data-testid="empty-state" />` },
  AppButton: { template: `<button><slot /></button>` },
}

describe("pipelines/index.vue", () => {
  it("renderiza um PipelineCard por pipeline", async () => {
    const wrapper = await mountSuspended(PipelinesIndexPage, {
      route: "/pipelines",
      global: { stubs },
    })
    expect(wrapper.findAll("[data-testid='pipeline-card']").length).toBe(2)
  })

  it("exibe EmptyState quando não há pipelines", async () => {
    mockStoreFn.mockReturnValueOnce({
      pipelines: [],
      loaded: true,
      load: vi.fn().mockResolvedValue(undefined),
    })
    const wrapper = await mountSuspended(PipelinesIndexPage, {
      route: "/pipelines",
      global: { stubs },
    })
    expect(wrapper.find("[data-testid='empty-state']").exists()).toBe(true)
    expect(wrapper.findAll("[data-testid='pipeline-card']").length).toBe(0)
  })
})
