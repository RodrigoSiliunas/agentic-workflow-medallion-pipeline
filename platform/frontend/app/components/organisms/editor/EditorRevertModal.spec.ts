import { mountSuspended } from "@nuxt/test-utils/runtime"
import { describe, it, expect } from "vitest"
import EditorRevertModal from "./EditorRevertModal.vue"
import type { PipelineEditSession } from "~/types/pipeline-editor-v2"

function makeSession(overrides: Partial<PipelineEditSession> = {}): PipelineEditSession {
  return {
    id: "sess-revert",
    status: "pr_created",
    ...overrides,
  } as PipelineEditSession
}

describe("EditorRevertModal", () => {
  it("renders 3 mode options", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const options = wrapper.findAll(".revert-option")
    expect(options).toHaveLength(3)
  })

  it("renders option titles: Reverter PR, Fechar PR sem reverter, Voltar para rascunho", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const text = wrapper.text()
    expect(text).toContain("Reverter PR")
    expect(text).toContain("Fechar PR sem reverter")
    expect(text).toContain("Voltar para rascunho")
  })

  it("default selected mode is revert_pr", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const options = wrapper.findAll(".revert-option")
    // First option (revert_pr) should have --selected class
    expect(options[0].classes()).toContain("revert-option--selected")
    expect(options[1].classes()).not.toContain("revert-option--selected")
    expect(options[2].classes()).not.toContain("revert-option--selected")
  })

  it("clicking an option changes selection to that option", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const options = wrapper.findAll(".revert-option")

    // Click second option (close_pr)
    await options[1].trigger("click")

    expect(options[0].classes()).not.toContain("revert-option--selected")
    expect(options[1].classes()).toContain("revert-option--selected")
    expect(options[2].classes()).not.toContain("revert-option--selected")
  })

  it("clicking third option selects draft mode", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const options = wrapper.findAll(".revert-option")
    await options[2].trigger("click")
    expect(options[2].classes()).toContain("revert-option--selected")
  })

  it("confirm button emits confirm('revert_pr') by default", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const confirmBtn = wrapper.findAll("button").find((b) => b.text().includes("Confirmar reversão"))
    expect(confirmBtn).toBeDefined()
    await confirmBtn!.trigger("click")

    const emitted = wrapper.emitted("confirm")
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toBe("revert_pr")
  })

  it("emits confirm('close_pr') after selecting close_pr option and clicking confirm", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const options = wrapper.findAll(".revert-option")
    await options[1].trigger("click") // select close_pr

    const confirmBtn = wrapper.findAll("button").find((b) => b.text().includes("Confirmar reversão"))
    await confirmBtn!.trigger("click")

    const emitted = wrapper.emitted("confirm")
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toBe("close_pr")
  })

  it("emits confirm('draft') after selecting draft option and clicking confirm", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const options = wrapper.findAll(".revert-option")
    await options[2].trigger("click") // select draft

    const confirmBtn = wrapper.findAll("button").find((b) => b.text().includes("Confirmar reversão"))
    await confirmBtn!.trigger("click")

    const emitted = wrapper.emitted("confirm")
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toBe("draft")
  })

  it("emits close when 'Cancelar' button is clicked", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const cancelBtn = wrapper.findAll("button").find((b) => b.text().includes("Cancelar"))
    expect(cancelBtn).toBeDefined()
    await cancelBtn!.trigger("click")
    expect(wrapper.emitted("close")).toBeTruthy()
  })

  it("shows session id in the body text", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession({ id: "sess-revert" }) },
    })
    expect(wrapper.text()).toContain("sess-revert")
  })

  it("is wrapped in EditorModalShell", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const shell = wrapper.findComponent({ name: "EditorModalShell" })
    expect(shell.exists()).toBe(true)
    expect(shell.props("title")).toBe("Reverter alteração")
  })

  it("shows selected mode code in .revert-selected-mode", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const selectedMode = wrapper.find(".revert-selected-mode")
    expect(selectedMode.exists()).toBe(true)
    expect(selectedMode.text()).toContain("revert_pr")
  })

  it("updates .revert-selected-mode when option changes", async () => {
    const wrapper = await mountSuspended(EditorRevertModal, {
      props: { open: true, session: makeSession() },
    })
    const options = wrapper.findAll(".revert-option")
    await options[1].trigger("click")

    const selectedMode = wrapper.find(".revert-selected-mode")
    expect(selectedMode.text()).toContain("close_pr")
  })
})
