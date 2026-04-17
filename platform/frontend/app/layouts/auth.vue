<template>
  <div
    class="min-h-screen flex items-center justify-center relative overflow-hidden"
    :style="{ background: 'var(--bg)' }"
  >
    <div class="hero-blur-purple top-[-100px] left-[20%]" />
    <div class="hero-blur-purple bottom-[-100px] right-[20%]" />
    <div
      class="w-full max-w-md p-8 rounded-[var(--radius-2xl)] border border-[var(--border)] bg-[var(--surface)]/80 backdrop-blur-sm relative z-10"
    >
      <div class="flex items-center gap-2.5 mb-8">
        <SafaLogo variant="icon" :size="32" />
        <div>
          <h1 class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">
            Flowertex Platform
          </h1>
          <p class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
            Pipeline agent
          </p>
        </div>
      </div>
      <slot />
    </div>
  </div>
</template>
