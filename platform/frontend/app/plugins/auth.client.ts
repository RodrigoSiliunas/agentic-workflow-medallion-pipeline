/**
 * Auth client plugin — restaura sessao do usuario no client.
 *
 * Tenta ler access_token do sessionStorage (sync, rapido). Se expirado ou
 * ausente, tenta refresh via httpOnly cookie (async, ~100ms). O middleware
 * so roda depois desse plugin completar, entao a sessao esta pronta.
 *
 * O sufixo `.client.ts` garante que so roda no browser (nunca no SSR).
 */
export default defineNuxtPlugin(async () => {
  const auth = useAuthStore()
  await auth.initFromStorage()
})
