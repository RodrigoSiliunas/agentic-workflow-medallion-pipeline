import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import EditorMessageBubble from "./EditorMessageBubble.vue"
import type { EditorChatMessage } from "~/types/pipeline-editor-v2"

describe("EditorMessageBubble", () => {
  it("renderiza mensagem do usuário com autor", async () => {
    const message: EditorChatMessage = {
      role: "user",
      content: "Renomeia cliente_id",
      author: "Rodrigo",
      time: "14:30",
    }
    const wrapper = await mountSuspended(EditorMessageBubble, { props: { message } })
    expect(wrapper.text()).toContain("Rodrigo")
    expect(wrapper.text()).toContain("Renomeia cliente_id")
    expect(wrapper.text()).toContain("14:30")
  })

  it("renderiza mensagem do assistente com label 'Pipeline agent'", async () => {
    const message: EditorChatMessage = {
      role: "assistant",
      content: "Proposta gerada com sucesso.",
      time: "14:31",
    }
    const wrapper = await mountSuspended(EditorMessageBubble, { props: { message } })
    expect(wrapper.text()).toContain("Pipeline agent")
    expect(wrapper.text()).toContain("Proposta gerada")
  })

  it("mensagem do usuário fica em flex-row-reverse", async () => {
    const message: EditorChatMessage = { role: "user", content: "ok" }
    const wrapper = await mountSuspended(EditorMessageBubble, { props: { message } })
    expect(wrapper.classes().join(" ")).toContain("flex-row-reverse")
  })

  it("mensagem do assistente fica em flex-row", async () => {
    const message: EditorChatMessage = { role: "assistant", content: "ok" }
    const wrapper = await mountSuspended(EditorMessageBubble, { props: { message } })
    expect(wrapper.classes().join(" ")).toContain("flex-row")
  })

  it("exibe typing-dots quando streaming=true e sem conteúdo", async () => {
    const message: EditorChatMessage = { role: "assistant", content: "", streaming: true }
    const wrapper = await mountSuspended(EditorMessageBubble, { props: { message } })
    expect(wrapper.findAll(".typing-dot").length).toBe(3)
  })

  it("não exibe typing-dots quando há conteúdo", async () => {
    const message: EditorChatMessage = { role: "assistant", content: "Resposta", streaming: true }
    const wrapper = await mountSuspended(EditorMessageBubble, { props: { message } })
    expect(wrapper.findAll(".typing-dot").length).toBe(0)
  })

  it("usa 'Você' como autor padrão para user sem author", async () => {
    const message: EditorChatMessage = { role: "user", content: "oi" }
    const wrapper = await mountSuspended(EditorMessageBubble, { props: { message } })
    expect(wrapper.text()).toContain("Você")
  })
})
