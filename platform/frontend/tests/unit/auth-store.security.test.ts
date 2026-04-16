/**
 * Security guard (T2 Phase 1): access_token jamais persiste em
 * sessionStorage/localStorage. Teste estático contra o source.
 *
 * Mitiga regressão: PRs futuros não devem reintroduzir
 * `sessionStorage.setItem("access_token", ...)` ou
 * `sessionStorage.getItem("access_token")` (leitura).
 * `removeItem("access_token")` é permitido (legacy cleanup).
 */
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { describe, expect, it } from "vitest"

const AUTH_STORE = resolve(__dirname, "../../app/stores/auth.ts")
const SOURCE = readFileSync(AUTH_STORE, "utf8")

describe("auth store — token handling (T2)", () => {
  it("never stores access_token in sessionStorage", () => {
    expect(SOURCE).not.toMatch(/sessionStorage\.setItem\s*\(\s*["']access_token["']/)
  })

  it("never stores access_token in localStorage", () => {
    expect(SOURCE).not.toMatch(/localStorage\.setItem\s*\(\s*["']access_token["']/)
  })

  it("never reads access_token via sessionStorage.getItem", () => {
    expect(SOURCE).not.toMatch(/sessionStorage\.getItem\s*\(\s*["']access_token["']/)
  })

  it("never reads access_token via localStorage.getItem", () => {
    expect(SOURCE).not.toMatch(/localStorage\.getItem\s*\(\s*["']access_token["']/)
  })

  it("allows removeItem('access_token') for legacy cleanup", () => {
    // Legacy removal is OK — garante que sessions pre-upgrade limpam o
    // token antigo caso ainda exista.
    const matches = SOURCE.match(
      /sessionStorage\.removeItem\s*\(\s*["']access_token["']/g,
    )
    expect(matches).not.toBeNull()
    expect(matches!.length).toBeGreaterThanOrEqual(1)
  })

  it("calls refresh() on init to restore session from httpOnly cookie", () => {
    expect(SOURCE).toMatch(/await\s+this\.refresh\(\)/)
  })

  it("logout clears in-memory accessToken", () => {
    expect(SOURCE).toMatch(/this\.accessToken\s*=\s*null/)
  })
})
