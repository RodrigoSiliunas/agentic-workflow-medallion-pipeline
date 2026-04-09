<template>
  <div class="flex h-screen" style="background: var(--bg-primary); color: var(--text-primary)">
    <!-- Sidebar -->
    <aside
      class="w-[280px] flex-shrink-0 flex flex-col border-r overflow-hidden"
      style="background: var(--bg-surface); border-color: var(--border-default)"
    >
      <!-- Logo -->
      <div class="p-4 border-b" style="border-color: var(--border-default)">
        <h1 class="text-lg font-semibold">Namastex</h1>
        <p class="text-xs" style="color: var(--text-tertiary)">Pipeline Agent</p>
      </div>

      <!-- Pipeline + Thread navigation -->
      <div class="flex-1 overflow-y-auto py-2">
        <SidebarNav :pipelines="pipelines" />
      </div>

      <!-- User info -->
      <div class="p-3 border-t" style="border-color: var(--border-default)">
        <div class="flex items-center gap-2">
          <UAvatar :text="authStore.userName?.charAt(0)" size="sm" />
          <div class="flex-1 min-w-0">
            <p class="text-sm truncate">{{ authStore.userName }}</p>
            <p class="text-xs truncate" style="color: var(--text-tertiary)">{{ authStore.userRole }}</p>
          </div>
          <UButton
            v-if="authStore.canManageSettings"
            variant="ghost"
            icon="i-heroicons-cog-6-tooth"
            size="xs"
            @click="navigateTo('/settings')"
          />
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 flex flex-col overflow-hidden">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const { pipelines } = usePipelines()
</script>
