/**
 * Global auth middleware — redirect para /login se nao autenticado.
 */
export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuthStore()

  // Inicializar do localStorage na primeira carga
  if (!auth.initialized) {
    auth.initFromStorage()
  }

  // Rotas publicas
  const publicRoutes = ["/login", "/register"]
  if (publicRoutes.includes(to.path)) {
    // Redirect para chat se ja logado
    if (auth.isLoggedIn) return navigateTo("/chat")
    return
  }

  // Rota protegida — verificar auth
  if (!auth.isLoggedIn) {
    return navigateTo(`/login?redirect=${encodeURIComponent(to.fullPath)}`)
  }
})
