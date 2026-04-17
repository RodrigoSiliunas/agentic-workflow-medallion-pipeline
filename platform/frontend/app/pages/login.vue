<template>
  <div>
    <h2
      class="text-2xl font-semibold mb-1 tracking-tight"
      :style="{ color: 'var(--text-primary)' }"
    >
      Entrar
    </h2>
    <p class="text-sm mb-6" :style="{ color: 'var(--text-secondary)' }">
      Acesse sua conta para conversar com os agentes do pipeline.
    </p>

    <form class="space-y-4" @submit.prevent="handleLogin">
      <AppInput
        v-model="email"
        label="Email"
        type="email"
        placeholder="rodrigo@flowertex.com"
      />

      <AppInput
        v-model="password"
        label="Senha"
        type="password"
        placeholder="********"
      />

      <AppButton type="submit" :loading="loading" class="w-full justify-center">
        Entrar
      </AppButton>

      <p
        v-if="error"
        class="text-xs text-center"
        :style="{ color: 'var(--status-error)' }"
      >
        {{ error }}
      </p>

      <p v-if="isMock" class="text-[11px] text-center" :style="{ color: 'var(--text-tertiary)' }">
        Modo mock: qualquer credencial funciona.
      </p>
    </form>

    <div
      class="mt-6 pt-4 border-t text-center text-xs"
      :style="{ borderColor: 'var(--border)', color: 'var(--text-tertiary)' }"
    >
      Novo por aqui?
      <NuxtLink
        to="/register"
        class="ml-1 font-medium"
        :style="{ color: 'var(--brand-500)' }"
      >
        Criar conta
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "auth" })

const auth = useAuthStore()
const route = useRoute()
const config = useRuntimeConfig()

const email = ref("")
const password = ref("")
const loading = ref(false)
const error = ref("")
const isMock = computed(() => config.public.mockMode)

// Redirect pos-hydration se ja estiver logado (o middleware pula rotas
// publicas durante hydration pra evitar mismatch de layout).
onMounted(() => {
  if (auth.isLoggedIn) {
    navigateTo((route.query.redirect as string) || "/chat", { replace: true })
  }
})

async function handleLogin() {
  loading.value = true
  error.value = ""
  try {
    await auth.login(email.value, password.value)
    const redirect = (route.query.redirect as string) || "/chat"
    navigateTo(redirect)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Erro ao entrar"
  } finally {
    loading.value = false
  }
}
</script>
