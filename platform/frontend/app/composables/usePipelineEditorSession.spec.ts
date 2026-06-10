/**
 * Testes do usePipelineEditorSession — state machine, sendNL, runPreview, confirmApprove.
 * Usa mock mode (NUXT_PUBLIC_MOCK_MODE=true por padrão nos testes).
 */
import { describe, it, expect } from "vitest"
import { defineComponent, nextTick, ref } from "vue"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import type { PipelineWorkspace } from "~/types/pipeline-editor-v2"

const MOCK_WS: PipelineWorkspace = {
  id: "test_pipeline",
  name: "Test Pipeline",
  description: null,
  databricksJobId: null,
  githubRepo: null,
  config: {},
  manifest: {
    templateSlug: "test",
    displayName: "Test",
    nodes: [{
      id: "silver_messages",
      layer: "silver",
      taskKey: "silver_messages",
      filePath: "test.py",
      inputTables: ["bronze.messages"],
      outputTables: ["silver.messages"],
      supportedOperations: ["rename_column"],
      insertionMarker: "# EDITOR",
    }],
  },
}

function makeTestComp(workspaceValue: PipelineWorkspace = MOCK_WS) {
  return defineComponent({
    setup() {
      const workspace = ref(workspaceValue)
      const session = usePipelineEditorSession(workspace)
      return { session }
    },
    template: `<div />`,
  })
}

describe("usePipelineEditorSession — estado inicial", () => {
  it("inicia com stateMachine=idle e sem mensagens", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    expect(session.stateMachine.value).toBe("idle")
    expect(session.messages.value).toHaveLength(0)
    expect(session.isStreaming.value).toBe(false)
  })

  it("mode inicial é 'chat'", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    expect(session.mode.value).toBe("chat")
  })

  it("canApprove=false sem preview", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    expect(session.canApprove.value).toBe(false)
  })
})

describe("usePipelineEditorSession — derivação de mode e sourceOfTruth", () => {
  it("mode='builder' quando sourceOfTruth=builder sem chatEdits", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    session.sourceOfTruth.value = "builder"
    session.builderEdits.value = true
    await nextTick()
    expect(session.mode.value).toBe("builder")
  })

  it("mode='hibrido' quando chatEdits E builderEdits são true", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    session.chatEdits.value = true
    session.builderEdits.value = true
    await nextTick()
    expect(session.mode.value).toBe("hibrido")
  })

  it("mode='chat' com sourceOfTruth=null", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    session.sourceOfTruth.value = null
    await nextTick()
    expect(session.mode.value).toBe("chat")
  })
})

describe("usePipelineEditorSession — canApprove matriz", () => {
  it("canApprove=false quando preview=null", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    session.preview.value = null
    expect(session.canApprove.value).toBe(false)
  })

  it("canApprove=false quando preview.status=running", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    session.preview.value = { status: "running" }
    session.validation.value = { valid: true, checks: [] }
    expect(session.canApprove.value).toBe(false)
  })

  // A validação (C2) roda DENTRO do approve no backend (e revalida a cada
  // tentativa) — falha anterior NÃO trava o botão; o gate é só preview+PR.
  it("canApprove=true mesmo com validation.valid=false (validação roda no approve)", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    session.preview.value = { status: "ready" }
    session.validation.value = { valid: false, checks: [] }
    expect(session.canApprove.value).toBe(true)
  })

  // Regressão do deadlock: validation só nasce DEPOIS do primeiro approve —
  // com ela nula e preview pronto, o botão TEM que estar habilitado.
  it("canApprove=true com preview=ready e validation=null", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    session.preview.value = { status: "ready" }
    session.validation.value = null
    session.stateMachine.value = "idle"
    expect(session.canApprove.value).toBe(true)
  })

  it("canApprove=false quando stateMachine=pr_created", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    session.preview.value = { status: "ready" }
    session.validation.value = { valid: true, checks: [] }
    session.stateMachine.value = "pr_created"
    expect(session.canApprove.value).toBe(false)
  })

  it("canApprove=true quando preview=ready, validation.valid=true, não pr_created", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    session.preview.value = { status: "ready" }
    session.validation.value = { valid: true, checks: [] }
    session.stateMachine.value = "idle"
    expect(session.canApprove.value).toBe(true)
  })
})

describe("usePipelineEditorSession — sendNL (mock mode)", () => {
  it("sendNL: adiciona mensagem do usuário, streaming, depois proposta", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }

    // Inicia sendNL sem await para observar estados intermediários
    const promise = session.sendNL("Renomeie cliente_id para customer_id")
    await nextTick()

    // Imediatamente: isStreaming=true, stateMachine=generating_proposal
    expect(session.isStreaming.value).toBe(true)
    expect(session.stateMachine.value).toBe("generating_proposal")
    expect(session.messages.value[0].role).toBe("user")
    expect(session.messages.value[0].content).toBe("Renomeie cliente_id para customer_id")

    // Aguarda mock delay (~1200ms no mock)
    await promise

    // Depois: proposta recebida
    expect(session.isStreaming.value).toBe(false)
    expect(session.stateMachine.value).toBe("idle")
    expect(session.messages.value.some((m) => m.role === "assistant" && m.proposal)).toBe(true)
    expect(session.currentProposal.value).not.toBeNull()
    expect(session.draft.value).not.toBeNull()
  }, 10000)
})

describe("usePipelineEditorSession — runPreview (mock mode)", () => {
  it("runPreview: previewRunning=true→false, preview.status=ready", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }

    // Precisa de uma sessão ativa — simula através do store
    const store = usePipelinesStore()
    store.editSessions = [{
      id: "test_ses", pipelineId: "test_pipeline", title: "Teste",
      status: "draft", targetLayers: ["silver"], baseRef: "dev",
      draftBranch: null, currentVersionId: null,
    }]
    store.activeEditSessionId = "test_ses"

    const promise = session.runPreview()
    await nextTick()
    expect(session.previewRunning.value).toBe(true)
    expect(session.stateMachine.value).toBe("running_preview")

    await promise
    expect(session.previewRunning.value).toBe(false)
    expect(session.preview.value?.status).toBe("ready")
    expect(session.stateMachine.value).toBe("idle")
  }, 10000)
})

describe("usePipelineEditorSession — caminho de erro", () => {
  it("dismissError limpa o erro e volta para idle", async () => {
    const wrapper = await mountSuspended(makeTestComp())
    const { session } = wrapper.vm as { session: ReturnType<typeof usePipelineEditorSession> }
    session.error.value = { title: "Erro", message: "Falha" }
    session.stateMachine.value = "error"
    session.dismissError()
    await nextTick()
    expect(session.error.value).toBeNull()
    expect(session.stateMachine.value).toBe("idle")
  })
})

describe("pickDefaultTargetNode — último escritor da tabela", () => {
  const mk = (id: string, table: string) => ({
    id, layer: "silver" as const, taskKey: id, filePath: id,
    inputTables: [], outputTables: [table], supportedOperations: [],
    insertionMarker: "#",
  })

  it("escolhe o ÚLTIMO node que escreve a mesma tabela (reescritor)", () => {
    const nodes = [
      mk("silver_dedup", "cat.silver.messages_clean"),
      mk("silver_entities", "cat.silver.messages_clean"),
      mk("silver_enrichment", "cat.silver.conversations_enriched"),
    ]
    expect(pickDefaultTargetNode(nodes)?.id).toBe("silver_entities")
  })

  it("com escritor único, mantém o primeiro node", () => {
    const nodes = [
      mk("silver_a", "cat.silver.t1"),
      mk("silver_b", "cat.silver.t2"),
    ]
    expect(pickDefaultTargetNode(nodes)?.id).toBe("silver_a")
  })

  it("lista vazia retorna null", () => {
    expect(pickDefaultTargetNode([])).toBeNull()
  })
})
