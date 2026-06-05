import { describe, expect, it, vi } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import KebabMenu from "./KebabMenu.vue"

const ITEMS = [
  { label: "Editar", icon: "pencil-square", onClick: vi.fn() },
  { label: "Excluir", icon: "trash", danger: true, onClick: vi.fn() },
]

describe("KebabMenu", () => {
  it("renderiza o botão trigger", async () => {
    const wrapper = await mountSuspended(KebabMenu, { props: { items: ITEMS } })
    expect(wrapper.find("button").exists()).toBe(true)
  })

  it("dropdown fechado por padrão", async () => {
    await mountSuspended(KebabMenu, { props: { items: ITEMS } })
    // O dropdown é teleportado — antes de clicar não deve existir no body
    expect(document.body.textContent).not.toContain("Editar")
  })

  it("abre dropdown ao clicar no trigger", async () => {
    const wrapper = await mountSuspended(KebabMenu, { props: { items: ITEMS } })
    await wrapper.find("button").trigger("click")
    expect(document.body.innerHTML).toContain("Editar")
    expect(document.body.innerHTML).toContain("Excluir")
  })

  it("chama onClick do item via handleItemClick", async () => {
    const onClick = vi.fn()
    const wrapper = await mountSuspended(KebabMenu, {
      props: { items: [{ label: "Ação", onClick }] },
    })
    // Acessa método exposto para simular clique em item do dropdown
    type Exposed = { handleItemClick: (item: { label: string; onClick?: () => void }) => void; open: boolean }
    const vm = wrapper.vm as unknown as Exposed
    vm.handleItemClick({ label: "Ação", onClick })
    expect(onClick).toHaveBeenCalled()
    // Dropdown fecha após clicar
    expect(vm.open).toBe(false)
  })

  it("item danger tem cor de erro", async () => {
    const wrapper = await mountSuspended(KebabMenu, { props: { items: ITEMS } })
    await wrapper.find("button").trigger("click")
    const items = document.body.querySelectorAll("[role='menuitem']")
    const dangerItem = Array.from(items).find((el) => el.textContent?.includes("Excluir"))
    expect((dangerItem as HTMLElement)?.style?.color || dangerItem?.getAttribute("style")).toContain(
      "var(--status-error)",
    )
  })
})
