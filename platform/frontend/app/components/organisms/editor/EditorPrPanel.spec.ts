import { mountSuspended } from "@nuxt/test-utils/runtime"
import { describe, it, expect } from "vitest"
import EditorPrPanel from "./EditorPrPanel.vue"
import type {
  EditProposal,
  PreviewResultV2,
  ValidationResult,
  PipelineEditSession,
} from "~/types/pipeline-editor-v2"

function makeSession(overrides: Partial<PipelineEditSession> = {}): PipelineEditSession {
  return {
    id: "sess-123",
    status: "idle",
    prNumber: undefined,
    ...overrides,
  } as PipelineEditSession
}

function makeProposal(overrides: Partial<EditProposal> = {}): EditProposal {
  return {
    explanation: "explanation",
    draft: { operations: [] },
    filesAffected: [],
    riskScore: 2,
    testPlan: [],
    ...overrides,
  } as EditProposal
}

function makePreview(status: string): PreviewResultV2 {
  return { status } as PreviewResultV2
}

function makeValidation(valid: boolean): ValidationResult {
  return {
    valid,
    checks: [{ label: "Codegen PySpark", state: valid ? "ok" : "fail" }],
  } as ValidationResult
}

describe("EditorPrPanel — approve logic matrix", () => {
  // Case 1: no preview → canApprove=false, blockMsg contains "Rode o preview"
  it("Case 1: no preview — approve button is disabled, block message shown", async () => {
    const wrapper = await mountSuspended(EditorPrPanel, {
      props: {
        proposal: makeProposal(),
        preview: null,
        validation: null,
        session: makeSession(),
        fileDiffs: [],
      },
    })
    // Approve button should be disabled
    const approveBtn = wrapper.findAll("button").find((b) => b.text().includes("Aprovar"))
    expect(approveBtn).toBeDefined()
    expect(approveBtn!.attributes("disabled")).toBeDefined()

    // Block message contains "Rode o preview"
    const blockMsg = wrapper.find(".block-msg")
    expect(blockMsg.exists()).toBe(true)
    expect(blockMsg.text()).toContain("Rode o preview")
  })

  // Case 2: preview.status="running" → canApprove=false, blockMsg contains "não está pronto"
  it("Case 2: preview running — approve button disabled, block message about not ready", async () => {
    const wrapper = await mountSuspended(EditorPrPanel, {
      props: {
        proposal: makeProposal(),
        preview: makePreview("running"),
        validation: null,
        session: makeSession(),
        fileDiffs: [],
      },
    })
    const approveBtn = wrapper.findAll("button").find((b) => b.text().includes("Aprovar"))
    expect(approveBtn!.attributes("disabled")).toBeDefined()

    const blockMsg = wrapper.find(".block-msg")
    expect(blockMsg.exists()).toBe(true)
    expect(blockMsg.text()).toContain("não está pronto")
  })

  // Case 3: preview OK but validation.valid=false → canApprove=false, blockMsg contains "Validação"
  it("Case 3: preview ready but validation failed — approve disabled, Validação in block msg", async () => {
    const wrapper = await mountSuspended(EditorPrPanel, {
      props: {
        proposal: makeProposal(),
        preview: makePreview("ready"),
        validation: makeValidation(false),
        session: makeSession(),
        fileDiffs: [],
      },
    })
    const approveBtn = wrapper.findAll("button").find((b) => b.text().includes("Aprovar"))
    expect(approveBtn!.attributes("disabled")).toBeDefined()

    const blockMsg = wrapper.find(".block-msg")
    expect(blockMsg.exists()).toBe(true)
    expect(blockMsg.text()).toContain("Validação")
  })

  // Case 4: pr_created → canApprove=false, blockMsg="PR já aberto", shows "Ver PR" link not approve btn
  it("Case 4: pr_created — shows clickable Ver PR link, not approve button", async () => {
    const wrapper = await mountSuspended(EditorPrPanel, {
      props: {
        proposal: makeProposal(),
        preview: makePreview("ready"),
        validation: makeValidation(true),
        session: makeSession({
          status: "pr_created",
          prNumber: 42,
          prUrl: "https://github.com/acme/repo/pull/42",
        }),
        fileDiffs: [],
      },
    })

    // "Ver PR #42" deve ser um link clicavel para o PR no GitHub
    const verPrLink = wrapper.findAll("a").find((a) => a.text().includes("Ver PR #42"))
    expect(verPrLink).toBeDefined()
    expect(verPrLink!.attributes("href")).toContain("/pull/42")

    // Approve button should NOT be in the DOM (pr_created branch renders different template)
    const approveBtn = wrapper.findAll("button").find((b) =>
      b.text().trim() === "Aprovar e abrir PR"
    )
    expect(approveBtn).toBeUndefined()

    // blockMsg element should not exist for pr_created (condition: !canApprove && session.status !== 'pr_created')
    const blockMsg = wrapper.find(".block-msg")
    expect(blockMsg.exists()).toBe(false)
  })

  // Case 5: preview.status="ready" && validation.valid=true && status!="pr_created" → canApprove=true
  it("Case 5: all conditions met — approve button is enabled", async () => {
    const wrapper = await mountSuspended(EditorPrPanel, {
      props: {
        proposal: makeProposal(),
        preview: makePreview("ready"),
        validation: makeValidation(true),
        session: makeSession({ status: "idle" }),
        fileDiffs: [],
      },
    })
    const approveBtn = wrapper.findAll("button").find((b) => b.text().includes("Aprovar"))
    expect(approveBtn).toBeDefined()
    expect(approveBtn!.attributes("disabled")).toBeUndefined()

    // No block message shown when can approve
    expect(wrapper.find(".block-msg").exists()).toBe(false)
  })

  // Emit tests
  it("emits approve on approve button click (when canApprove=true)", async () => {
    const wrapper = await mountSuspended(EditorPrPanel, {
      props: {
        proposal: makeProposal(),
        preview: makePreview("ready"),
        validation: makeValidation(true),
        session: makeSession(),
        fileDiffs: [],
      },
    })
    const approveBtn = wrapper.findAll("button").find((b) => b.text().includes("Aprovar"))
    await approveBtn!.trigger("click")
    expect(wrapper.emitted("approve")).toBeTruthy()
  })

  it("emits share on share button click", async () => {
    const wrapper = await mountSuspended(EditorPrPanel, {
      props: {
        proposal: makeProposal(),
        preview: makePreview("ready"),
        validation: makeValidation(true),
        session: makeSession(),
        fileDiffs: [],
      },
    })
    const shareBtn = wrapper.findAll("button").find((b) => b.text().includes("Compartilhar"))
    expect(shareBtn).toBeDefined()
    await shareBtn!.trigger("click")
    expect(wrapper.emitted("share")).toBeTruthy()
  })

  it("emits revert on revert button click (pr_created state)", async () => {
    const wrapper = await mountSuspended(EditorPrPanel, {
      props: {
        proposal: makeProposal(),
        preview: makePreview("ready"),
        validation: makeValidation(true),
        session: makeSession({ status: "pr_created", prNumber: 42 }),
        fileDiffs: [],
      },
    })
    const revertBtn = wrapper.findAll("button").find((b) => b.text().includes("Reverter"))
    expect(revertBtn).toBeDefined()
    await revertBtn!.trigger("click")
    expect(wrapper.emitted("revert")).toBeTruthy()
  })
})
