/**
 * Catalogo de LLM providers + models pra UI multi-provider.
 *
 * Provider IDs casam com observer.chat.{anthropic,openai,google}
 * registrados no backend (factory create_chat_provider).
 *
 * Pricing snapshot 2026-04 (USD por 1M tokens, input/output).
 */

export type LLMProviderId = "anthropic" | "openai" | "google"

export interface LLMModel {
  id: string
  label: string
  tier: "premium" | "balanced" | "fast"
  pricePer1M: { input: number; output: number }
  contextWindow: number
}

export interface LLMProvider {
  id: LLMProviderId
  label: string
  apiKeyType: string
  shortDescription: string
  capabilities: {
    tools: boolean
    vision: boolean
    streaming: boolean
    promptCaching: boolean
  }
  models: LLMModel[]
}

export const LLM_PROVIDERS: LLMProvider[] = [
  {
    id: "anthropic",
    label: "Anthropic Claude",
    apiKeyType: "anthropic_api_key",
    shortDescription: "Melhor pra codigo + analise tecnica",
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      promptCaching: true,
    },
    models: [
      {
        id: "claude-opus-4-7",
        label: "Opus 4.7 (premium)",
        tier: "premium",
        pricePer1M: { input: 15, output: 75 },
        contextWindow: 1_000_000,
      },
      {
        id: "claude-sonnet-4-6",
        label: "Sonnet 4.6 (balanced)",
        tier: "balanced",
        pricePer1M: { input: 3, output: 15 },
        contextWindow: 200_000,
      },
      {
        id: "claude-haiku-4-5",
        label: "Haiku 4.5 (fast)",
        tier: "fast",
        pricePer1M: { input: 0.8, output: 4 },
        contextWindow: 200_000,
      },
    ],
  },
  {
    id: "openai",
    label: "OpenAI GPT",
    apiKeyType: "openai_api_key",
    shortDescription: "Generalista, multimodal forte, ecossistema amplo",
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      promptCaching: false,
    },
    models: [
      {
        id: "gpt-5",
        label: "GPT-5 (premium)",
        tier: "premium",
        pricePer1M: { input: 10, output: 30 },
        contextWindow: 1_000_000,
      },
      {
        id: "gpt-5-mini",
        label: "GPT-5 Mini (balanced)",
        tier: "balanced",
        pricePer1M: { input: 0.15, output: 0.6 },
        contextWindow: 400_000,
      },
      {
        id: "gpt-4o",
        label: "GPT-4o (fast)",
        tier: "fast",
        pricePer1M: { input: 5, output: 15 },
        contextWindow: 128_000,
      },
    ],
  },
  {
    id: "google",
    label: "Google Gemini",
    apiKeyType: "google_api_key",
    shortDescription: "Custo baixo, contexto longo (2M), latencia baixa",
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      promptCaching: true,
    },
    models: [
      {
        id: "gemini-2.5-pro",
        label: "Gemini 2.5 Pro (premium)",
        tier: "premium",
        pricePer1M: { input: 1.25, output: 5 },
        contextWindow: 2_000_000,
      },
      {
        id: "gemini-2.5-flash",
        label: "Gemini 2.5 Flash (balanced)",
        tier: "balanced",
        pricePer1M: { input: 0.075, output: 0.3 },
        contextWindow: 1_000_000,
      },
      {
        id: "gemini-2.0-flash",
        label: "Gemini 2.0 Flash (fast)",
        tier: "fast",
        pricePer1M: { input: 0.075, output: 0.3 },
        contextWindow: 1_000_000,
      },
    ],
  },
]

export function useLLMProviders() {
  return {
    providers: LLM_PROVIDERS,
    findProvider(id: string): LLMProvider | undefined {
      return LLM_PROVIDERS.find((p) => p.id === id)
    },
    findModel(providerId: string, modelId: string): LLMModel | undefined {
      const provider = LLM_PROVIDERS.find((p) => p.id === providerId)
      return provider?.models.find((m) => m.id === modelId)
    },
    /** Retorna lista flat agrupada pra dropdowns. */
    allModels(): Array<{ provider: LLMProviderId; model: LLMModel }> {
      return LLM_PROVIDERS.flatMap((p) =>
        p.models.map((m) => ({ provider: p.id, model: m })),
      )
    },
    formatPrice(model: LLMModel): string {
      return `$${model.pricePer1M.input}/$${model.pricePer1M.output} per 1M tokens`
    },
  }
}
