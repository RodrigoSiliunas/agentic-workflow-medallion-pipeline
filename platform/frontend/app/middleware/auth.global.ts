/**
 * Global auth middleware — redirect para /login se nao autenticado.
 *
 * Inicializacao do auth store acontece via plugin `auth.client.ts`
 * (que roda apos hydration com acesso a localStorage). No SSR, o
 * state fica vazio e o middleware libera rotas publicas sem redirect.
 */
export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuthStore()
  const nuxtApp = useNuxtApp()

  // Fallback de seguranca — se por alguma razao o plugin nao rodou,
  // tenta inicializar aqui (idempotente: no-op em SSR, le localStorage
  // no client).
  if (!auth.initialized) {
    auth.initFromStorage()
  }

  const publicRoutes = ["/", "/login", "/register"]
  if (publicRoutes.includes(to.path)) {
    // Se ja logado, pula rotas publicas (login, register, landing).
    //
    // IMPORTANTE: nao redirecionamos durante hydration. O SSR renderiza
    // a pagina publica (auth/landing layout) porque nao tem acesso ao
    // localStorage. Se redirecionarmos aqui DURANTE hydration, o Vue
    // tenta reconciliar o HTML do SSR (layout antigo) com o vdom do
    // /chat (layout novo), gerando "Hydration class mismatch". A pagina
    // (`index.vue`, `login.vue`, `register.vue`) usa `onMounted` para
    // redirecionar apos hydration.
    if (import.meta.client && nuxtApp.isHydrating) return
    if (auth.isLoggedIn) return navigateTo("/chat")
    return
  }

  if (!auth.isLoggedIn) {
    return navigateTo(`/login?redirect=${encodeURIComponent(to.fullPath)}`)
  }
})
