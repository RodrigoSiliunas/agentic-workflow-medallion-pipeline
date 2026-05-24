/**
 * HTTP client com token refresh automatico.
 *
 * Envia `credentials: 'include'` em todas as requests pra que o httpOnly
 * cookie do refresh_token viaje automaticamente nas calls pro backend.
 * O access_token vai no header Authorization (lido do Pinia memory).
 */
export function useApiClient() {
  const config = useRuntimeConfig()
  const auth = useAuthStore()
  const baseURL = config.public.apiBase as string

  async function request<T>(
    path: string,
    options: RequestInit & { params?: Record<string, string> } = {},
  ): Promise<T> {
    const url = new URL(`${baseURL}${path}`)
    if (options.params) {
      Object.entries(options.params).forEach(([k, v]) => url.searchParams.set(k, v))
    }

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    }

    if (auth.accessToken) {
      headers.Authorization = `Bearer ${auth.accessToken}`
    }

    const response = await fetch(url.toString(), {
      ...options,
      headers,
      credentials: "include",
    })

    // Token expirado — refresh via cookie e retry
    if (response.status === 401) {
      await auth.refresh()
      if (auth.accessToken) {
        headers.Authorization = `Bearer ${auth.accessToken}`
        const retry = await fetch(url.toString(), {
          ...options,
          headers,
          credentials: "include",
        })
        if (!retry.ok) throw new Error(await retry.text())
        if (retry.status === 204) return undefined as T
        return retry.json()
      }
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      // FastAPI manda detail como string ou como objeto estruturado (ex:
      // { code: "credential_missing", ... }). Preservar o objeto na
      // propriedade `detail` permite que o caller faca branching por codigo.
      const detail = error.detail
      const message =
        typeof detail === "string"
          ? detail
          : (detail as { message?: string })?.message || response.statusText
      const err = new Error(message) as Error & {
        status: number
        detail: unknown
      }
      err.status = response.status
      err.detail = detail
      throw err
    }

    // 204 No Content — retorna undefined (ex: DELETE responses)
    if (response.status === 204) return undefined as T

    return response.json()
  }

  async function downloadBlob(path: string, filename?: string) {
    const url = new URL(`${baseURL}${path}`)
    const headers: Record<string, string> = {}
    if (auth.accessToken) {
      headers.Authorization = `Bearer ${auth.accessToken}`
    }

    const response = await fetch(url.toString(), {
      method: "GET",
      headers,
      credentials: "include",
    })

    if (!response.ok) {
      throw new Error(await response.text())
    }

    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = objectUrl
    anchor.download = filename || path.split("/").pop() || "download"
    anchor.click()
    URL.revokeObjectURL(objectUrl)
  }

  return {
    baseURL,
    get: <T>(path: string, params?: Record<string, string>) =>
      request<T>(path, { method: "GET", params }),
    post: <T>(path: string, body?: unknown) =>
      request<T>(path, { method: "POST", body: JSON.stringify(body) }),
    put: <T>(path: string, body?: unknown) =>
      request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
    delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
    downloadBlob,
  }
}
