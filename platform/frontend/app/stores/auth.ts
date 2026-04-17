/**
 * Auth store — login, logout, refresh, role getters.
 *
 * Seguranca (T2 hardening):
 * - **access_token**: SOMENTE em memoria (Pinia). NUNCA tocado por
 *   sessionStorage/localStorage — mitiga roubo via XSS.
 * - **refresh_token**: httpOnly cookie setado pelo backend (7 dias).
 *   NUNCA acessivel via JavaScript — protegido contra XSS.
 *
 * Fluxo de sessao:
 * 1. Login/Register → backend seta cookie + retorna access_token no body
 * 2. Navegacao normal → access_token no header Authorization (memoria)
 * 3. Access token expira → POST /auth/refresh (cookie auto-enviado) → novo
 * 4. Nova aba / reload → memoria vazia → `initFromStorage` chama
 *    `/auth/refresh`; se cookie valido, recria sessao; senao, fica
 *    anonimo ate proximo login.
 * 5. Logout → POST /auth/logout (limpa cookie) + limpa estado em memoria
 */
import { defineStore } from "pinia"

interface User {
  id: string
  email: string
  name: string
  role: "root" | "admin" | "editor" | "viewer"
  companyId: string
}

interface AuthState {
  user: User | null
  accessToken: string | null
  initialized: boolean
}

const ROLE_HIERARCHY: Record<string, number> = {
  root: 4,
  admin: 3,
  editor: 2,
  viewer: 1,
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    user: null,
    accessToken: null,
    initialized: false,
  }),

  getters: {
    isLoggedIn: (state) => !!state.accessToken && !!state.user,
    userRole: (state) => state.user?.role || "viewer",
    userName: (state) => state.user?.name || "",
    isRoot: (state) => state.user?.role === "root",
    isAdmin: (state) => (ROLE_HIERARCHY[state.user?.role || ""] ?? 0) >= 3,
    isEditor: (state) => (ROLE_HIERARCHY[state.user?.role || ""] ?? 0) >= 2,
    canManageSettings: (state) => (ROLE_HIERARCHY[state.user?.role || ""] ?? 0) >= 3,
    canManageUsers: (state) => (ROLE_HIERARCHY[state.user?.role || ""] ?? 0) >= 3,
    canCreatePR: (state) => (ROLE_HIERARCHY[state.user?.role || ""] ?? 0) >= 2,
  },

  actions: {
    async login(email: string, password: string) {
      const config = useRuntimeConfig()

      if (config.public.mockMode) {
        this.accessToken = "mock-access-token"
        this.user = {
          id: "mock-user-1",
          email: email || "rodrigo@flowertex.com",
          name: "Rodrigo Siliunas",
          role: "admin",
          companyId: "flowertex",
        }
        if (import.meta.client) {
          // access_token fica em memoria; `mock_user` persiste apenas pra
          // devX (reload de dev server) — nunca contem credenciais.
          sessionStorage.setItem("mock_user", JSON.stringify(this.user))
        }
        return
      }

      try {
        const data = await $fetch<{
          access_token: string
          refresh_token: string
        }>(`${config.public.apiBase}/auth/login`, {
          method: "POST",
          body: { email, password },
          credentials: "include",
        })

        this.accessToken = data.access_token
        await this.fetchUser()
      } catch (e: unknown) {
        const detail =
          (e as { data?: { detail?: string }; message?: string })?.data?.detail ??
          (e instanceof Error ? e.message : "Login falhou")
        throw new Error(detail)
      }
    },

    async register(payload: {
      companyName: string
      companySlug: string
      adminName: string
      adminEmail: string
      adminPassword: string
    }) {
      const config = useRuntimeConfig()

      if (config.public.mockMode) {
        await this.login(payload.adminEmail, payload.adminPassword)
        if (this.user) {
          this.user.name = payload.adminName
          this.user.email = payload.adminEmail
          this.user.companyId = payload.companySlug
        }
        return
      }

      try {
        const data = await $fetch<{
          access_token: string
          refresh_token: string
        }>(`${config.public.apiBase}/auth/register-company`, {
          method: "POST",
          body: {
            company_name: payload.companyName,
            company_slug: payload.companySlug,
            admin_name: payload.adminName,
            admin_email: payload.adminEmail,
            admin_password: payload.adminPassword,
          },
          credentials: "include",
        })

        this.accessToken = data.access_token
        await this.fetchUser()
      } catch (e: unknown) {
        const detail =
          (e as { data?: { detail?: string }; message?: string })?.data?.detail ??
          (e instanceof Error ? e.message : "Falha no registro")
        throw new Error(detail)
      }
    },

    async fetchUser() {
      if (!this.accessToken) return

      try {
        const parts = this.accessToken.split(".")
        if (parts.length !== 3 || !parts[1]) throw new Error("invalid jwt")
        const payload = JSON.parse(atob(parts[1])) as {
          sub: string
          company_id?: string
          role?: string
        }
        this.user = {
          id: payload.sub,
          email: "",
          name: "",
          role: (payload.role as User["role"]) || "viewer",
          companyId: payload.company_id || "",
        }
      } catch {
        this.logout()
        return
      }

      const config = useRuntimeConfig()
      if (config.public.mockMode) return

      try {
        const profile = await $fetch<{
          id: string
          email: string
          name: string
          role: string
        }>(`${config.public.apiBase}/users/me`, {
          headers: { Authorization: `Bearer ${this.accessToken}` },
        })
        if (this.user) {
          this.user.email = profile.email
          this.user.name = profile.name
          this.user.role = profile.role as User["role"]
        }
      } catch {
        // /users/me opcional — continua com o que veio do JWT
      }
    },

    async refresh() {
      const config = useRuntimeConfig()
      try {
        // O refresh_token viaja via httpOnly cookie (credentials: 'include').
        // Nao mandamos no body — o backend le do cookie.
        const data = await $fetch<{
          access_token: string
          refresh_token: string
        }>(`${config.public.apiBase}/auth/refresh`, {
          method: "POST",
          credentials: "include",
        })

        this.accessToken = data.access_token
        await this.fetchUser()
      } catch {
        this.logout()
      }
    },

    async logout() {
      const config = useRuntimeConfig()
      // Limpa cookie httpOnly no backend
      if (!config.public.mockMode) {
        try {
          await $fetch(`${config.public.apiBase}/auth/logout`, {
            method: "POST",
            credentials: "include",
          })
        } catch {
          // ignora — cookie vai expirar eventualmente
        }
      }
      this.user = null
      this.accessToken = null
      if (import.meta.client) {
        // Legacy cleanup: releases antigas persistiam access_token em
        // sessionStorage. Removemos caso ainda exista de uma sessao
        // pre-upgrade.
        sessionStorage.removeItem("access_token")
        sessionStorage.removeItem("mock_user")
      }
    },

    async initFromStorage() {
      const config = useRuntimeConfig()

      // Mock mode — auto-login
      if (config.public.mockMode) {
        if (import.meta.client) {
          const stored = sessionStorage.getItem("mock_user")
          if (stored) {
            try {
              this.user = JSON.parse(stored)
            } catch {
              // ignora
            }
          }
        }
        if (!this.user) {
          this.user = {
            id: "mock-user-1",
            email: "rodrigo@flowertex.com",
            name: "Rodrigo Siliunas",
            role: "admin",
            companyId: "flowertex",
          }
        }
        this.accessToken = "mock-access-token"
        if (import.meta.client) {
          sessionStorage.setItem("mock_user", JSON.stringify(this.user))
        }
        this.initialized = true
        return
      }

      if (!import.meta.client) return

      // T2 hardening: access_token NAO persiste mais em sessionStorage.
      // Em reload / nova aba, memoria esta vazia — pedimos refresh via
      // cookie httpOnly. Backend responde 200 com novo access_token se o
      // refresh cookie ainda for valido, ou 401 se o usuario deslogou.
      //
      // Remover artefato legado (pre-upgrade) pra nao vazar o token antigo.
      sessionStorage.removeItem("access_token")

      try {
        await this.refresh()
      } catch {
        // Sem cookie valido — usuario nao esta logado
      }
      this.initialized = true
    },
  },
})
