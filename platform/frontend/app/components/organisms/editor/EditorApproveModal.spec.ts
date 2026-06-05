import { mountSuspended } from "@nuxt/test-utils/runtime"
import { describe, it, expect } from "vitest"
import EditorApproveModal from "./EditorApproveModal.vue"
import type { PipelineEditSession, EditProposal } from "~/types/pipeline-editor-v2"

function makeSession(overrides: Partial<PipelineEditSession> = {}): PipelineEditSession {
  return {
    id: "session-abc",
    status: "idle",
    ...overrides,
  } as PipelineEditSession
}

function makeProposal(overrides: Partial<EditProposal> = {}): EditProposal {
  return {
    explanation: "Fix the pipeline",
    draft: { operations: [] },
    files_affected: ["silver/dedup_clean.py"],
    risk_score: 3,
    test_plan: ["Run validation checks"],
    ...overrides,
  } as EditProposal
}

describe("EditorApproveModal", () => {
  it("is not rendered when open=false", async () => {
    const wrapper = await mountSuspended(EditorApproveModal, {
      props: {
        open: false,
        session: makeSession(),
        proposal: makeProposal(),
        preview: null,
      },
    })
    expect(wrapper.find(".approve-body").exists()).toBe(false)
  })

  it("is rendered when open=true", async () => {
    const wrapper = await mountSuspended(EditorApproveModal, {
      props: {
        open: true,
        session: makeSession(),
        proposal: makeProposal(),
        preview: null,
      },
    })
    expect(wrapper.find(".approve-body").exists()).toBe(true)
  })

  it("shows branch as pipeline-editor/{session.id}", async () => {
    const wrapper = await mountSuspended(EditorApproveModal, {
      props: {
        open: true,
        session: makeSession({ id: "session-abc" }),
        proposal: makeProposal(),
        preview: null,
      },
    })
    expect(wrapper.text()).toContain("pipeline-editor/session-abc")
  })

  it("shows base as 'dev'", async () => {
    const wrapper = await mountSuspended(EditorApproveModal, {
      props: {
        open: true,
        session: makeSession(),
        proposal: makeProposal(),
        preview: null,
      },
    })
    // The base ref "dev" appears in multiple places (description and meta grid)
    const metaGrid = wrapper.find(".approve-meta-grid")
    expect(metaGrid.text()).toContain("dev")
  })

  it("is rendered inside EditorModalShell", async () => {
    const wrapper = await mountSuspended(EditorApproveModal, {
      props: {
        open: true,
        session: makeSession(),
        proposal: makeProposal(),
        preview: null,
      },
    })
    const shell = wrapper.findComponent({ name: "EditorModalShell" })
    expect(shell.exists()).toBe(true)
  })

  it("passes correct title to EditorModalShell", async () => {
    const wrapper = await mountSuspended(EditorApproveModal, {
      props: {
        open: true,
        session: makeSession(),
        proposal: makeProposal(),
        preview: null,
      },
    })
    const shell = wrapper.findComponent({ name: "EditorModalShell" })
    expect(shell.props("title")).toBe("Aprovar e abrir PR")
  })

  it("emits confirm when 'Criar PR' button is clicked", async () => {
    const wrapper = await mountSuspended(EditorApproveModal, {
      props: {
        open: true,
        session: makeSession(),
        proposal: makeProposal(),
        preview: null,
      },
    })
    const confirmBtn = wrapper.findAll("button").find((b) => b.text().includes("Criar PR"))
    expect(confirmBtn).toBeDefined()
    await confirmBtn!.trigger("click")
    expect(wrapper.emitted("confirm")).toBeTruthy()
  })

  it("emits close when 'Cancelar' button is clicked", async () => {
    const wrapper = await mountSuspended(EditorApproveModal, {
      props: {
        open: true,
        session: makeSession(),
        proposal: makeProposal(),
        preview: null,
      },
    })
    const cancelBtn = wrapper.findAll("button").find((b) => b.text().includes("Cancelar"))
    expect(cancelBtn).toBeDefined()
    await cancelBtn!.trigger("click")
    expect(wrapper.emitted("close")).toBeTruthy()
  })

  it("shows files_affected list when proposal has files", async () => {
    const wrapper = await mountSuspended(EditorApproveModal, {
      props: {
        open: true,
        session: makeSession(),
        proposal: makeProposal({ files_affected: ["silver/dedup_clean.py", "gold/analytics.py"] }),
        preview: null,
      },
    })
    expect(wrapper.text()).toContain("silver/dedup_clean.py")
    expect(wrapper.text()).toContain("gold/analytics.py")
  })

  it("session id is used in branch name correctly", async () => {
    const wrapper = await mountSuspended(EditorApproveModal, {
      props: {
        open: true,
        session: makeSession({ id: "xyz-999" }),
        proposal: makeProposal(),
        preview: null,
      },
    })
    expect(wrapper.text()).toContain("pipeline-editor/xyz-999")
  })
})
