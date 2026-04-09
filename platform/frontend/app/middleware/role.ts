/**
 * Role middleware — protege rotas por role.
 * Uso: definePageMeta({ middleware: ['role'], role: 'admin' })
 */
export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuthStore()
  const requiredRole = to.meta.role as string | undefined

  if (!requiredRole) return

  const hierarchy: Record<string, number> = {
    root: 4,
    admin: 3,
    editor: 2,
    viewer: 1,
  }

  const userLevel = hierarchy[auth.userRole] || 0
  const requiredLevel = hierarchy[requiredRole] || 0

  if (userLevel < requiredLevel) {
    return navigateTo("/chat")
  }
})
