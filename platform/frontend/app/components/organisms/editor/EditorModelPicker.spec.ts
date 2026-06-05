import { mountSuspended } from "@nuxt/test-utils/runtime"
import { describe, it, expect } from "vitest"
import EditorModelPicker from "./EditorModelPicker.vue"
import { MODEL_PROVIDERS } from "./constants"

// Total models = 3 Anthropic + 2 OpenAI + 2 Databricks = 7
const TOTAL_MODELS = MODEL_PROVIDERS.flatMap((p) => p.models).length

describe("EditorModelPicker", () => {
  it("shows all 7 models in the dropdown when opened", async () => {
    const wrapper = await mountSuspended(EditorModelPicker, {
      props: { providerId: "anthropic", modelId: "claude-sonnet-4.6" },
    })

    // Open the dropdown
    const trigger = wrapper.find(".trigger-btn")
    await trigger.trigger("click")

    const modelItems = wrapper.findAll(".model-item")
    expect(modelItems).toHaveLength(TOTAL_MODELS)
  })

  it("renders 3 provider section headers in the dropdown", async () => {
    const wrapper = await mountSuspended(EditorModelPicker, {
      props: { providerId: "anthropic", modelId: "claude-sonnet-4.6" },
    })
    await wrapper.find(".trigger-btn").trigger("click")

    const providerHeaders = wrapper.findAll(".provider-header")
    expect(providerHeaders).toHaveLength(3)

    const headerText = providerHeaders.map((h) => h.text())
    expect(headerText.some((t) => t.includes("Anthropic"))).toBe(true)
    expect(headerText.some((t) => t.includes("OpenAI"))).toBe(true)
    expect(headerText.some((t) => t.includes("Databricks"))).toBe(true)
  })

  it("shows 'padrão' pill on claude-sonnet-4.6", async () => {
    const wrapper = await mountSuspended(EditorModelPicker, {
      props: { providerId: "anthropic", modelId: "claude-sonnet-4.6" },
    })
    await wrapper.find(".trigger-btn").trigger("click")

    // Find the model item for sonnet
    const modelItems = wrapper.findAll(".model-item")
    const sonnetItem = modelItems.find((item) => item.text().includes("Claude Sonnet 4.6"))
    expect(sonnetItem).toBeDefined()
    expect(sonnetItem!.text()).toContain("padrão")
  })

  it("emits change with (providerId, modelId) when a model is clicked", async () => {
    const wrapper = await mountSuspended(EditorModelPicker, {
      props: { providerId: "anthropic", modelId: "claude-sonnet-4.6" },
    })
    await wrapper.find(".trigger-btn").trigger("click")

    // Click on GPT-5 (OpenAI)
    const modelItems = wrapper.findAll(".model-item")
    const gpt5Item = modelItems.find((item) => item.text().includes("GPT-5"))
    expect(gpt5Item).toBeDefined()
    await gpt5Item!.trigger("click")

    const emitted = wrapper.emitted("change")
    expect(emitted).toBeTruthy()
    expect(emitted![0]).toEqual(["openai", "gpt-5"])
  })

  it("closes the dropdown after selecting a model", async () => {
    const wrapper = await mountSuspended(EditorModelPicker, {
      props: { providerId: "anthropic", modelId: "claude-sonnet-4.6" },
    })
    await wrapper.find(".trigger-btn").trigger("click")
    expect(wrapper.find(".dropdown").exists()).toBe(true)

    const modelItems = wrapper.findAll(".model-item")
    await modelItems[0].trigger("click")

    expect(wrapper.find(".dropdown").exists()).toBe(false)
  })

  it("dropdown is closed by default", async () => {
    const wrapper = await mountSuspended(EditorModelPicker, {
      props: { providerId: "anthropic", modelId: "claude-sonnet-4.6" },
    })
    expect(wrapper.find(".dropdown").exists()).toBe(false)
  })

  it("dropdown opens on trigger click", async () => {
    const wrapper = await mountSuspended(EditorModelPicker, {
      props: { providerId: "anthropic", modelId: "claude-sonnet-4.6" },
    })
    await wrapper.find(".trigger-btn").trigger("click")
    expect(wrapper.find(".dropdown").exists()).toBe(true)
  })

  it("trigger button has aria-expanded=true when dropdown is open", async () => {
    const wrapper = await mountSuspended(EditorModelPicker, {
      props: { providerId: "anthropic", modelId: "claude-sonnet-4.6" },
    })
    const trigger = wrapper.find(".trigger-btn")
    expect(trigger.attributes("aria-expanded")).toBe("false")
    await trigger.trigger("click")
    expect(trigger.attributes("aria-expanded")).toBe("true")
  })

  it("marks active model with model-item--active class", async () => {
    const wrapper = await mountSuspended(EditorModelPicker, {
      props: { providerId: "openai", modelId: "gpt-5" },
    })
    await wrapper.find(".trigger-btn").trigger("click")

    const activeItems = wrapper.findAll(".model-item--active")
    expect(activeItems).toHaveLength(1)
    expect(activeItems[0].text()).toContain("GPT-5")
  })

  it("emits change with Databricks model when DBRX is clicked", async () => {
    const wrapper = await mountSuspended(EditorModelPicker, {
      props: { providerId: "anthropic", modelId: "claude-sonnet-4.6" },
    })
    await wrapper.find(".trigger-btn").trigger("click")

    const modelItems = wrapper.findAll(".model-item")
    const dbrxItem = modelItems.find((item) => item.text().includes("DBRX Instruct"))
    expect(dbrxItem).toBeDefined()
    await dbrxItem!.trigger("click")

    const emitted = wrapper.emitted("change")
    expect(emitted![0]).toEqual(["databricks", "dbrx-instruct"])
  })
})
