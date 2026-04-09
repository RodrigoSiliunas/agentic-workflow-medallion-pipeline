/**
 * Auth store — login, logout, refresh, role getters.
 * Padrão idlehub: token em cookie httpOnly ou localStorage.
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
  refreshToken: string | null
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
    refreshToken: null,
    initialized: false,
  }),

  getters: {
    isLoggedIn: (state) => !!state.accessToken && !!state.user,
    userRole: (state) => state.user?.role || "viewer",
    userName: (state) => state.user?.name || "",
    isRoot: (state) => state.user?.role === "root",
    isAdmin: (state) => ROLE_HIERARCHY[state.user?.role || ""] >= 3,
    isEditor: (state) => ROLE_HIERARCHY[state.user?.role || ""] >= 2,
    canManageSettings: (state) => ROLE_HIERARCHY[state.user?.role || ""] >= 3,
    canManageUsers: (state) => ROLE_HIERARCHY[state.user?.role || ""] >= 3,
    canCreatePR: (state) => ROLE_HIERARCHY[state.user?.role || ""] >= 2,
  },

  actions: {
    async login(email: string, password: string) {
      const config = useRuntimeConfig()
      const { data, error } = await useFetch<{
        access_token: string
        refresh_token: string
      }>(`${config.public.apiBase}/auth/login`, {
        method: "POST",
        body: { email, password },
      })

      if (error.value) throw new Error(error.value.data?.detail || "Login falhou")

      this.accessToken = data.value!.access_token
      this.refreshToken = data.value!.refresh_token
      await this.fetchUser()

      // Persistir tokens
      if (import.meta.client) {
        localStorage.setItem("access_token", this.accessToken!)
        localStorage.setItem("refresh_token", this.refreshToken!)
      }
    },

    async fetchUser() {
      if (!this.accessToken) return
      const config = useRuntimeConfig()
      try {
        // Decode JWT para pegar user info (sem chamada extra)
        const payload = JSON.parse(atob(this.accessToken.split(".")[1]))
        this.user = {
          id: payload.sub,
          email: payload.email || "",
          name: payload.name || "",
          role: payload.role || "viewer",
          companyId: payload.company_id || "",
        }
      } catch {
        this.logout()
      }
    },

    async refresh() {
      if (!this.refreshToken) return
      const config = useRuntimeConfig()
      try {
        const { data } = await useFetch<{
          access_token: string
          refresh_token: string
        }>(`${config.public.apiBase}/auth/refresh`, {
          method: "POST",
          body: { refresh_token: this.refreshToken },
        })

        if (data.value) {
          this.accessToken = data.value.access_token
          this.refreshToken = data.value.refresh_token
          if (import.meta.client) {
            localStorage.setItem("access_token", this.accessToken)
            localStorage.setItem("refresh_token", this.refreshToken)
          }
          await this.fetchUser()
        }
      } catch {
        this.logout()
      }
    },

    logout() {
      this.user = null
      this.accessToken = null
      this.refreshToken = null
      if (import.meta.client) {
        localStorage.removeItem("access_token")
        localStorage.removeItem("refresh_token")
      }
      navigateTo("/login")
    },

    initFromStorage() {
      if (!import.meta.client) return
      this.accessToken = localStorage.getItem("access_token")
      this.refreshToken = localStorage.getItem("refresh_token")
      if (this.accessToken) {
        this.fetchUser()
      }
      this.initialized = true
    },
  },
})
