import { mountSuspended } from "@nuxt/test-utils/runtime"
import { describe, it, expect } from "vitest"
import ProposalCard from "./ProposalCard.vue"
import type { EditProposal } from "~/types/pipeline-editor-v2"

const mockProposal: EditProposal = {
  explanation: "Test explanation",
  draft: {
    operations: [
      { op: "rename_column", column: "a", new_name: "b" },
    ],
  },
  files_affected: ["file.py"],
  risk_score: 4.5,
  test_plan: ["Check count"],
}

describe("ProposalCard", () => {
  it("renders the explanation text", async () => {
    const wrapper = await mountSuspended(ProposalCard, {
      props: { proposal: mockProposal },
    })
    expect(wrapper.text()).toContain("Test explanation")
  })

  it("renders OpMiniRow for each operation (v-for ops)", async () => {
    const wrapper = await mountSuspended(ProposalCard, {
      props: { proposal: mockProposal },
    })
    const opRows = wrapper.findAllComponents({ name: "OpMiniRow" })
    expect(opRows).toHaveLength(mockProposal.draft.operations.length)
  })

  it("renders files_affected as chips", async () => {
    const wrapper = await mountSuspended(ProposalCard, {
      props: { proposal: mockProposal },
    })
    expect(wrapper.text()).toContain("file.py")
  })

  it("renders test_plan checklist items", async () => {
    const wrapper = await mountSuspended(ProposalCard, {
      props: { proposal: mockProposal },
    })
    expect(wrapper.text()).toContain("Check count")
  })

  it("renders AppRiskGauge with the correct score prop", async () => {
    const wrapper = await mountSuspended(ProposalCard, {
      props: { proposal: mockProposal },
    })
    const gauge = wrapper.findComponent({ name: "AppRiskGauge" })
    expect(gauge.exists()).toBe(true)
    expect(gauge.props("value")).toBe(4.5)
  })

  it("emits preview when 'Rodar preview' button is clicked", async () => {
    const wrapper = await mountSuspended(ProposalCard, {
      props: { proposal: mockProposal },
    })
    const buttons = wrapper.findAll("button")
    const previewBtn = buttons.find((b) => b.text().includes("Rodar preview"))
    expect(previewBtn).toBeDefined()
    await previewBtn!.trigger("click")
    expect(wrapper.emitted("preview")).toBeTruthy()
  })

  it("emits adjustInBuilder when 'Ajustar no builder' button is clicked", async () => {
    const wrapper = await mountSuspended(ProposalCard, {
      props: { proposal: mockProposal },
    })
    const buttons = wrapper.findAll("button")
    const adjustBtn = buttons.find((b) => b.text().includes("Ajustar no builder"))
    expect(adjustBtn).toBeDefined()
    await adjustBtn!.trigger("click")
    expect(wrapper.emitted("adjustInBuilder")).toBeTruthy()
  })

  it("emits apply when 'Aplicar ao rascunho' button is clicked", async () => {
    const wrapper = await mountSuspended(ProposalCard, {
      props: { proposal: mockProposal },
    })
    const buttons = wrapper.findAll("button")
    const applyBtn = buttons.find((b) => b.text().includes("Aplicar ao rascunho"))
    expect(applyBtn).toBeDefined()
    await applyBtn!.trigger("click")
    expect(wrapper.emitted("apply")).toBeTruthy()
  })

  it("shows operation count in header", async () => {
    const wrapper = await mountSuspended(ProposalCard, {
      props: { proposal: mockProposal },
    })
    expect(wrapper.text()).toContain("1 operação")
  })

  it("shows plural operation count when more than 1 op", async () => {
    const proposal: EditProposal = {
      ...mockProposal,
      draft: {
        operations: [
          { op: "rename_column", column: "a", new_name: "b" },
          { op: "drop_column", column: "x" },
        ],
      },
    }
    const wrapper = await mountSuspended(ProposalCard, {
      props: { proposal },
    })
    expect(wrapper.text()).toContain("2 operações")
  })
})
