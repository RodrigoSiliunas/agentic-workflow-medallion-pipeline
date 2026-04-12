<template>
  <div>
    <h2
      class="text-2xl font-semibold mb-1 tracking-tight"
      :style="{ color: 'var(--text-primary)' }"
    >
      Criar conta
    </h2>
    <p class="text-sm mb-6" :style="{ color: 'var(--text-secondary)' }">
      Registre sua empresa e o usuário administrador em uma única etapa.
    </p>

    <form class="space-y-4" @submit.prevent="handleRegister">
      <!-- Empresa -->
      <div class="space-y-1.5">
        <p
          class="text-[10px] font-semibold uppercase tracking-wider"
          :style="{ color: 'var(--text-tertiary)' }"
        >
          Empresa
        </p>
        <AppInput
          v-model="form.companyName"
          label="Nome da empresa"
          placeholder="Safatechx Labs"
          :error="errors.companyName"
        />
        <AppInput
          v-model="form.companySlug"
          label="Slug"
          placeholder="safatechx"
          helper="Identificador único (só letras minúsculas, números e hífen)"
          :error="errors.companySlug"
          @update:model-value="onSlugInput"
        />
      </div>

      <!-- Admin -->
      <div class="space-y-1.5 pt-2">
        <p
          class="text-[10px] font-semibold uppercase tracking-wider"
          :style="{ color: 'var(--text-tertiary)' }"
        >
          Usuário administrador
        </p>
        <AppInput
          v-model="form.adminName"
          label="Nome completo"
          placeholder="Rodrigo Siliunas"
          :error="errors.adminName"
        />
        <AppInput
          v-model="form.adminEmail"
          label="Email"
          type="email"
          placeholder="rodrigo@safatechx.com"
          helper="Domínio precisa ser válido (ex: .com, .ai, .io)"
          :error="errors.adminEmail"
        />
        <AppInput
          v-model="form.adminPassword"
          label="Senha"
          type="password"
          placeholder="********"
          helper="Mínimo 8 caracteres"
          :error="errors.adminPassword"
        />
      </div>

      <AppButton type="submit" :loading="loading" class="w-full justify-center">
        Criar conta
      </AppButton>

      <p
        v-if="serverError"
        class="text-xs text-center"
        :style="{ color: 'var(--status-error)' }"
      >
        {{ serverError }}
      </p>

      <p v-if="isMock" class="text-[11px] text-center" :style="{ color: 'var(--text-tertiary)' }">
        Modo mock: registro não vai persistir de verdade.
      </p>
    </form>

    <div
      class="mt-6 pt-4 border-t text-center text-xs"
      :style="{ borderColor: 'var(--border)', color: 'var(--text-tertiary)' }"
    >
      Já tem conta?
      <NuxtLink
        to="/login"
        class="ml-1 font-medium"
        :style="{ color: 'var(--brand-500)' }"
      >
        Entrar
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "auth" })

const auth = useAuthStore()
const config = useRuntimeConfig()

const form = reactive({
  companyName: "",
  companySlug: "",
  adminName: "",
  adminEmail: "",
  adminPassword: "",
})

const errors = reactive({
  companyName: "",
  companySlug: "",
  adminName: "",
  adminEmail: "",
  adminPassword: "",
})

const loading = ref(false)
const serverError = ref("")
const isMock = computed(() => config.public.mockMode)

// Redirect pos-hydration se ja estiver logado (o middleware pula rotas
// publicas durante hydration pra evitar mismatch de layout).
onMounted(() => {
  if (auth.isLoggedIn) {
    navigateTo("/chat", { replace: true })
  }
})

const SLUG_REGEX = /^[a-z0-9]+(-[a-z0-9]+)*$/

function onSlugInput(value: string) {
  // Normaliza pra minúsculo + troca espaços por hífen enquanto o user digita
  form.companySlug = value.toLowerCase().replace(/\s+/g, "-")
}

function validate(): boolean {
  let ok = true
  for (const k of Object.keys(errors) as Array<keyof typeof errors>) {
    errors[k] = ""
  }

  if (form.companyName.trim().length < 2) {
    errors.companyName = "Mínimo 2 caracteres"
    ok = false
  }
  if (!SLUG_REGEX.test(form.companySlug)) {
    errors.companySlug = "Só minúsculas, números e hífen (ex: acme-labs)"
    ok = false
  }
  if (form.adminName.trim().length < 2) {
    errors.adminName = "Mínimo 2 caracteres"
    ok = false
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.adminEmail)) {
    errors.adminEmail = "Email inválido"
    ok = false
  }
  if (form.adminPassword.length < 8) {
    errors.adminPassword = "Mínimo 8 caracteres"
    ok = false
  }
  return ok
}

async function handleRegister() {
  serverError.value = ""
  if (!validate()) return

  loading.value = true
  try {
    await auth.register({
      companyName: form.companyName.trim(),
      companySlug: form.companySlug.trim(),
      adminName: form.adminName.trim(),
      adminEmail: form.adminEmail.trim(),
      adminPassword: form.adminPassword,
    })
    navigateTo("/chat")
  } catch (e: unknown) {
    serverError.value = e instanceof Error ? e.message : "Falha no registro"
  } finally {
    loading.value = false
  }
}
</script>
