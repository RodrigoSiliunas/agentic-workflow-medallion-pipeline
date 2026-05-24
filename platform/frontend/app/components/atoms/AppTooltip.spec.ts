import { describe, expect, it } from "vitest"
import { mountSuspended } from "@nuxt/test-utils/runtime"
import AppTooltip from "./AppTooltip.vue"

describe("AppTooltip", () => {
  it("renders label as data attribute", async () => {
    const wrapper = await mountSuspended(AppTooltip, {
      props: { label: "Ajuda" },
      slots: { default: "<button>btn</button>" },
    })
    expect(wrapper.attributes("data-label")).toBe("Ajuda")
  })

  it("renders slot content unmodified", async () => {
    const wrapper = await mountSuspended(AppTooltip, {
      props: { label: "Help" },
      slots: { default: "<button>OK</button>" },
    })
    expect(wrapper.html()).toContain("<button>OK</button>")
  })

  it("defaults to top position", async () => {
    const wrapper = await mountSuspended(AppTooltip, {
      props: { label: "X" },
    })
    expect(wrapper.attributes("data-position")).toBe("top")
  })

  it("respects custom position prop", async () => {
    const wrapper = await mountSuspended(AppTooltip, {
      props: { label: "X", position: "bottom" },
    })
    expect(wrapper.attributes("data-position")).toBe("bottom")
  })
})
