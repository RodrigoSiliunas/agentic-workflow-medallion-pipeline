<script setup lang="ts">
import type { PipelineEditSession } from "~/types/pipeline-editor-v2"

// Modal de compartilhamento de sessão do pipeline editor
const props = defineProps<{
  open: boolean
  session: PipelineEditSession
}>()

const emit = defineEmits<{
  close: []
}>()

// Estado local do modal
const expires = ref("7d")
const copied = ref(false)

// Opções de expiração do link
const expiresOptions = [
  { value: "1d", label: "1 dia" },
  { value: "7d", label: "7 dias" },
  { value: "30d", label: "30 dias" },
  { value: "never", label: "Nunca expira" }
]

// Opções de permissão (somente leitura no compartilhamento)
const permissionOptions = [{ value: "viewer", label: "Visualizador" }]

// Token derivado do id da sessão para o link compartilhável
const token = computed(() => {
  const base = props.session.id
  return btoa(base).replace(/=/g, "").substring(0, 24)
})

// URL pública de compartilhamento
const shareUrl = computed(
  () => `https://flowertex.app/shared/pipeline-edit/${token.value}`
)

// Ícone do botão de cópia
const copyIcon = computed(() => (copied.value ? "check" : "clipboard"))

// Copia o link para a área de transferência
async function copy() {
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 1500)
  } catch {
    // Fallback para browsers sem clipboard API
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 1500)
  }
}
</script>

<template>
  <EditorModalShell
    :open="open"
    title="Compartilhar sessão"
    icon="share"
    icon-tone="brand"
    :width="520"
    @close="emit('close')"
  >
    <!-- Corpo do modal de compartilhamento -->
    <div class="share-body">
      <!-- Descrição do funcionamento do link -->
      <p class="share-desc">
        Gere um link público para compartilhar esta sessão com outras pessoas.
        Quem receber o link poderá visualizar o rascunho e o preview, mas não editar.
      </p>

      <!-- Campo de link compartilhável -->
      <div class="share-link-section">
        <span class="share-link-label">Link público</span>
        <div class="share-link-row">
          <AppInput
            :model-value="shareUrl"
            icon="link"
            size="sm"
            class="share-url-input"
            readonly
          />
          <AppIconBtn
            :icon="copyIcon"
            label="Copiar link"
            :size="32"
            :active="copied"
            class="copy-btn"
            @click="copy"
          />
        </div>
      </div>

      <!-- Configurações do link em grid -->
      <div class="share-config-grid">
        <div class="config-item">
          <span class="config-label">Expiração</span>
          <AppSelect
            v-model="expires"
            :options="expiresOptions"
            size="sm"
          />
        </div>
        <div class="config-item">
          <span class="config-label">Permissão</span>
          <AppSelect
            model-value="viewer"
            :options="permissionOptions"
            size="sm"
          />
        </div>
      </div>

      <!-- Preview simulado da sessão compartilhada -->
      <div class="share-preview-box">
        <div class="preview-header">
          <div class="preview-skeleton preview-skeleton-title" />
          <div class="preview-skeleton preview-skeleton-pill" />
        </div>
        <div class="preview-body">
          <div class="preview-skeleton preview-skeleton-line" />
          <div class="preview-skeleton preview-skeleton-line preview-skeleton-short" />
          <div class="preview-skeleton preview-skeleton-line preview-skeleton-medium" />
        </div>
        <div class="preview-label">Prévia do link compartilhado</div>
      </div>
    </div>

    <!-- Rodapé com ações -->
    <template #footer>
      <div class="share-footer">
        <AppButton variant="ghost" color="neutral" size="sm" @click="emit('close')">
          Fechar
        </AppButton>
        <AppButton
          variant="solid"
          color="primary"
          size="sm"
          :icon="copyIcon"
          @click="copy"
        >
          {{ copied ? "Copiado!" : "Copiar link" }}
        </AppButton>
      </div>
    </template>
  </EditorModalShell>
</template>

<style scoped>
/* Corpo principal */
.share-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Descrição */
.share-desc {
  font-size: 14px;
  color: var(--fg-secondary);
  line-height: 1.6;
  margin: 0;
}

/* Seção do link */
.share-link-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.share-link-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--fg-secondary);
}

.share-link-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.share-url-input {
  flex: 1;
}

.copy-btn {
  flex-shrink: 0;
}

/* Grid de configurações */
.share-config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--fg-secondary);
}

/* Preview simulado com skeletons */
.share-preview-box {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  position: relative;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--surface-elevated);
  border-bottom: 1px solid var(--border);
}

.preview-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
}

/* Skeleton animado */
.preview-skeleton {
  background: var(--border);
  border-radius: var(--radius-sm);
  animation: skeleton-pulse 1.8s ease-in-out infinite;
}

.preview-skeleton-title {
  height: 14px;
  width: 60%;
}

.preview-skeleton-pill {
  height: 20px;
  width: 72px;
  border-radius: 999px;
}

.preview-skeleton-line {
  height: 10px;
  width: 100%;
}

.preview-skeleton-short {
  width: 45%;
}

.preview-skeleton-medium {
  width: 70%;
}

.preview-label {
  position: absolute;
  bottom: 8px;
  right: 10px;
  font-size: 11px;
  color: var(--fg-tertiary);
  pointer-events: none;
}

/* Rodapé */
.share-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@keyframes skeleton-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}
</style>
