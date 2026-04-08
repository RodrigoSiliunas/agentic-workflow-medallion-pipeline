export interface User {
  id: string
  email: string
  name: string
  role: UserRole
  companyId: string
}

export type UserRole = "admin" | "editor" | "viewer"
