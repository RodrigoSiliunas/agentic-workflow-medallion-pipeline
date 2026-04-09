/**
 * Proxy route — encaminha requests para o FastAPI backend.
 * Suporta SSE passthrough para streaming do chat.
 */
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const apiBase = config.public.apiBase as string

  // Reconstruir path
  const path = event.path?.replace("/api/proxy", "") || ""
  const targetUrl = `${apiBase}${path}`

  // Forward headers (incluindo Authorization)
  const headers: Record<string, string> = {}
  const authHeader = getHeader(event, "authorization")
  if (authHeader) headers.authorization = authHeader
  headers["content-type"] = getHeader(event, "content-type") || "application/json"

  // Forward request
  const method = event.method
  let body: string | undefined
  if (method !== "GET" && method !== "HEAD") {
    body = await readBody(event)
    if (typeof body === "object") body = JSON.stringify(body)
  }

  const response = await fetch(targetUrl, { method, headers, body })

  // SSE passthrough — se o backend retorna text/event-stream, repassar
  const contentType = response.headers.get("content-type") || ""
  if (contentType.includes("text/event-stream")) {
    setResponseHeader(event, "content-type", "text/event-stream")
    setResponseHeader(event, "cache-control", "no-cache")
    setResponseHeader(event, "connection", "keep-alive")
    return response.body
  }

  // JSON normal
  setResponseStatus(event, response.status)
  return response.json()
})
