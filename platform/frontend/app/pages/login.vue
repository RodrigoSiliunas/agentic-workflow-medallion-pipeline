<template>
  <div>
    <h2 class="text-2xl font-semibold mb-2" style="color: var(--text-primary)">Entrar</h2>
    <p class="text-sm mb-6" style="color: var(--text-secondary)">Acesse sua conta para conversar com seus pipelines</p>

    <form @submit.prevent="handleLogin" class="space-y-4">
      <UFormGroup label="Email">
        <UInput v-model="email" type="email" placeholder="seu@email.com" required />
      </UFormGroup>

      <UFormGroup label="Senha">
        <UInput v-model="password" type="password" placeholder="••••••••" required />
      </UFormGroup>

      <UButton type="submit" block :loading="loading">
        Entrar
      </UButton>

      <p v-if="error" class="text-sm text-center" style="color: var(--status-error)">
        {{ error }}
      </p>
    </form>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "auth" })

const auth = useAuthStore()
const route = useRoute()

const email = ref("")
const password = ref("")
const loading = ref(false)
const error = ref("")

async function handleLogin() {
  loading.value = true
  error.value = ""
  try {
    await auth.login(email.value, password.value)
    const redirect = (route.query.redirect as string) || "/chat"
    navigateTo(redirect)
  } catch (e: any) {
    error.value = e.message || "Erro ao entrar"
  } finally {
    loading.value = false
  }
}
</script>
