import { mountSuspended } from "@nuxt/test-utils/runtime"
import { describe, it, expect } from "vitest"
import DeployWizard from "./DeployWizard.vue"
import type { Template } from "~/types/template"

function makeTemplate(overrides: Partial<Template> = {}): Template {
  return {
    slug: "test-pipeline",
    name: "Test Pipeline",
    tagline: "Pipeline de teste",
    description: "Template para testes",
    category: "ETL",
    tags: [],
    icon: "i-heroicons-bolt",
    iconBg: "#000",
    version: "1.0.0",
    author: "test",
    deployCount: 0,
    durationEstimate: "5 min",
    architectureBullets: [],
    envSchema: [],
    changelog: [],
    published: true,
    ...overrides,
  }
}

async function goToCredentialsStep(wrapper: Awaited<ReturnType<typeof mountSuspended>>) {
  // config é reactive (não ref), então setupState.config é mutável diretamente
  const setupState = wrapper.getCurrentComponent().setupState as Record<string, unknown>
  const config = setupState.config as Record<string, unknown>
  ;(config as Record<string, string>).name = "meu-pipeline-prod"
  await wrapper.vm.$nextTick()

  const nextBtn = wrapper.findAll("button").find((b) => b.text().includes("Próximo"))
  if (nextBtn && !nextBtn.attributes("disabled")) {
    await nextBtn.trigger("click")
    await wrapper.vm.$nextTick()
  }
}

describe("DeployWizard — credentials step", () => {
  it("inclui github_repo no estado inicial das credenciais", async () => {
    const wrapper = await mountSuspended(DeployWizard, {
      props: { template: makeTemplate() },
    })
    const setupState = wrapper.getCurrentComponent().setupState as Record<string, unknown>
    const credentials = (setupState.config as Record<string, unknown>)
      .credentials as Record<string, string>
    expect(credentials).toHaveProperty("github_repo")
    expect(credentials.github_repo).toBe("")
  })

  it("exibe campo 'GitHub Repo (owner/repo)' na etapa de credenciais", async () => {
    const wrapper = await mountSuspended(DeployWizard, {
      props: { template: makeTemplate() },
    })
    await goToCredentialsStep(wrapper)
    expect(wrapper.text()).toContain("GitHub Repo")
  })

  it("exibe input com placeholder 'owner/repo' na etapa de credenciais", async () => {
    const wrapper = await mountSuspended(DeployWizard, {
      props: { template: makeTemplate() },
    })
    await goToCredentialsStep(wrapper)
    const input = wrapper.find("input[placeholder='owner/repo']")
    expect(input.exists()).toBe(true)
  })
})
