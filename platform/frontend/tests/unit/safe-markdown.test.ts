/**
 * T2 Phase 2 — Markdown sanitization tests.
 *
 * Verifica scheme allowlist: `javascript:`, `data:`, `vbscript:`, `file:`,
 * `blob:` e schemes arbitrários devem ser rejeitados. `http`, `https`,
 * `mailto`, `tel`, anchors e paths relativos passam.
 */
import { describe, expect, it } from "vitest"

import {
  escapeHtml,
  isSafeUrl,
  renderMarkdown,
} from "../../app/composables/useSafeMarkdown"

describe("isSafeUrl", () => {
  it.each([
    "https://example.com/path",
    "http://example.com",
    "mailto:foo@bar.com",
    "tel:+5511987654321",
    "#section",
    "/absolute/path",
    "./relative",
    "../parent",
    "page.html",
    "page?query=1",
  ])("accepts safe URL: %s", (url) => {
    expect(isSafeUrl(url)).toBe(true)
  })

  it.each([
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "jAvAsCrIpT:void(0)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "blob:http://example.com/abc",
    "about:blank",
    "chrome://settings",
    "ftp://example.com",
  ])("rejects dangerous URL: %s", (url) => {
    expect(isSafeUrl(url)).toBe(false)
  })

  it("rejects URLs with embedded control chars", () => {
    expect(isSafeUrl("java\tscript:alert(1)")).toBe(false)
    expect(isSafeUrl("java\nscript:alert(1)")).toBe(false)
  })

  it("rejects empty / whitespace", () => {
    expect(isSafeUrl("")).toBe(false)
    expect(isSafeUrl("   ")).toBe(false)
  })
})

describe("escapeHtml", () => {
  it("escapes all risky chars", () => {
    expect(escapeHtml("<script>\"'&")).toBe(
      "&lt;script&gt;&quot;&#39;&amp;",
    )
  })
})

describe("renderMarkdown — XSS surface", () => {
  it("blocks javascript: link, keeping label only", () => {
    const out = renderMarkdown("[click](javascript:alert(1))")
    expect(out).not.toContain("javascript:")
    expect(out).not.toContain("<a ")
    expect(out).toContain("click")
  })

  it("blocks data: link", () => {
    const out = renderMarkdown("[x](data:text/html,<script>alert(1)</script>)")
    expect(out).not.toContain("<script>") // escaped already
    expect(out).not.toContain("data:text/html")
    expect(out).not.toContain("<a ")
  })

  it("blocks vbscript: link", () => {
    const out = renderMarkdown("[x](vbscript:msgbox)")
    expect(out).not.toContain("vbscript:")
    expect(out).not.toContain("<a ")
  })

  it("allows https link with rel='noopener noreferrer'", () => {
    const out = renderMarkdown("[ok](https://example.com)")
    expect(out).toContain(`href="https://example.com"`)
    expect(out).toContain(`rel="noopener noreferrer"`)
    expect(out).toContain(`target="_blank"`)
  })

  it("escapes raw HTML in plain text", () => {
    const out = renderMarkdown("<img src=x onerror=alert(1)>")
    expect(out).not.toContain("<img")
    expect(out).toContain("&lt;img")
  })

  it("escapes HTML inside link label", () => {
    const out = renderMarkdown(
      "[<img onerror=alert(1)>](https://example.com)",
    )
    expect(out).not.toContain("<img")
    expect(out).toContain("&lt;img")
  })

  it("keeps legitimate markdown formatting", () => {
    const out = renderMarkdown("**bold** and `code`")
    expect(out).toContain("<strong>bold</strong>")
    expect(out).toContain("<code")
  })

  it("case-insensitive scheme check prevents bypass via capitalization", () => {
    const out = renderMarkdown("[x](JaVaScRiPt:alert(1))")
    expect(out).not.toContain("avaScr")
    expect(out).not.toContain("<a ")
  })
})
