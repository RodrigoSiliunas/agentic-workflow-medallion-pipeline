export interface ChatMessage {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  actions?: ActionResult[]
  attachments?: Attachment[]
  channel: "web" | "whatsapp" | "discord" | "telegram"
  timestamp: string
}

export interface ActionResult {
  type: "pr_created" | "run_triggered" | "query_executed" | "confirmation_required"
  status: "success" | "failed" | "pending"
  details: Record<string, unknown>
}

export interface Attachment {
  type: "image" | "file"
  name: string
  url: string
  mimeType: string
}

export interface Thread {
  id: string
  pipelineId: string
  title: string
  lastActivity: string
  messageCount: number
  channel: string
}
