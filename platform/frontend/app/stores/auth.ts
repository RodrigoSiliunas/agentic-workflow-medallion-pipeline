/**
 * Auth store — login, logout, refresh, role getters.
 *
 * Seguranca:
 * - **access_token**: Pinia memory + sessionStorage (15 min, limpo ao fechar aba).
 *   Necessario em memoria pra requests com Authorization header.
 * - **refresh_token**: httpOnly cookie setado pelo backend (7 dias).
 *   NUNCA acessivel via JavaScript — protegido contra XSS.
 *
 * Fluxo de sessao:
 * 1. Login/Register → backend seta cookie + retorna access_token no body
 * 2. Navegacao normal → access_token no header Authorization
 * 3. Access token expira → POST /auth/refresh (cookie auto-enviado) → novo access_token
 * 4. Nova aba/refresh → lê sessionStorage OU tenta refresh via cookie
 * 5. Logout → POST /auth/logout (limpa cookie) + limpa sessionStorage
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
          email: email || "rodrigo@safatechx.com",
          name: "Rodrigo Siliunas",
          role: "admin",
          companyId: "safatechx",
        }
        if (import.meta.client) {
          sessionStorage.setItem("access_token", this.accessToken)
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

        if (import.meta.client) {
          sessionStorage.setItem("access_token", this.accessToken)
        }
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

        if (import.meta.client) {
          sessionStorage.setItem("access_token", this.accessToken)
        }
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
        if (import.meta.client) {
          sessionStorage.setItem("access_token", this.accessToken)
        }
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
        sessionStorage.removeItem("access_token")
        sessionStorage.removeItem("mock_user")
      }
      navigateTo("/login")
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
            email: "rodrigo@safatechx.com",
            name: "Rodrigo Siliunas",
            role: "admin",
            companyId: "safatechx",
          }
        }
        this.accessToken = "mock-access-token"
        if (import.meta.client) {
          sessionStorage.setItem("access_token", this.accessToken)
          sessionStorage.setItem("mock_user", JSON.stringify(this.user))
        }
        this.initialized = true
        return
      }

      if (!import.meta.client) return

      // Tenta recuperar access_token do sessionStorage (sobrevive refresh da pagina)
      const storedAccess = sessionStorage.getItem("access_token")
      if (storedAccess) {
        try {
          const parts = storedAccess.split(".")
          if (parts.length !== 3 || !parts[1]) throw new Error("invalid")
          const payload = JSON.parse(atob(parts[1])) as {
            sub: string
            company_id?: string
            role?: string
            exp?: number
          }
          if (payload.exp && payload.exp * 1000 < Date.now()) {
            // Token expirado — tenta refresh via cookie
            sessionStorage.removeItem("access_token")
          } else {
            // Token valido — restaura sessao sync (rapido, sem API call)
            this.accessToken = storedAccess
            this.user = {
              id: payload.sub,
              email: "",
              name: "",
              role: (payload.role as User["role"]) || "viewer",
              companyId: payload.company_id || "",
            }
            void this.fetchUser()
            this.initialized = true
            return
          }
        } catch {
          sessionStorage.removeItem("access_token")
        }
      }

      // Sem access_token valido — tenta refresh via httpOnly cookie.
      // Se o usuario logou antes e nao fez logout, o cookie ainda existe.
      try {
        await this.refresh()
      } catch {
        // Sem cookie valido — usuario nao esta logado
      }
      this.initialized = true
    },
  },
})
