<template>
  <div class="relative">
    <!-- Grid pattern background (fundo) -->
    <div
      class="hero-grid pointer-events-none absolute inset-0"
      style="z-index: 0; mask-image: radial-gradient(ellipse at top, black 30%, transparent 65%)"
    />

    <!-- Hero signature blurs (fundo) -->
    <div
      class="hero-blur-purple pointer-events-none"
      style="z-index: 0; top: -200px; left: 50%; transform: translateX(-50%); opacity: 0.9"
    />
    <div
      class="hero-blur-purple pointer-events-none"
      style="z-index: 0; top: 30%; right: -300px; opacity: 0.4"
    />

    <!-- ============================================================ -->
    <!-- NAV BAR -->
    <!-- ============================================================ -->
    <nav class="relative z-20">
      <div
        class="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between"
      >
        <SafaLogo variant="lockup" :size="26" to="/" />

        <div class="flex items-center gap-2">
          <AppButton variant="ghost" size="sm" to="/login">Entrar</AppButton>
          <AppButton size="sm" to="/register">Criar conta</AppButton>
        </div>
      </div>
    </nav>

    <!-- ============================================================ -->
    <!-- HERO -->
    <!-- ============================================================ -->
    <section class="relative z-10">
      <div class="max-w-5xl mx-auto px-6 pt-20 pb-24 text-center">
        <!-- Badge — estilo ngrok (label + separador + texto + arrow) -->
        <NuxtLink
          to="/register"
          class="hero-badge group/badge"
        >
          <span class="hero-badge__label">NOVO</span>
          <span class="hero-badge__divider" />
          <span class="hero-badge__text">Agentic Data Platform · v1.0 beta</span>
          <span
            class="hero-badge__arrow transition-transform duration-300 group-hover/badge:translate-x-0.5"
          >→</span>
        </NuxtLink>

        <!-- Headline com rainbow shimmer animado -->
        <h1
          class="text-5xl sm:text-6xl md:text-7xl mb-6 max-w-4xl mx-auto"
          :style="{
            letterSpacing: '-0.03em',
            lineHeight: '1.02',
            fontFamily: 'var(--font-display)',
            fontWeight: 400,
            color: 'var(--text-primary)',
          }"
        >
          Pipelines de dados que
          <span class="block italic text-rainbow-purple">
            corrigem a si mesmos.
          </span>
        </h1>

        <!-- Subheadline -->
        <p
          class="text-base sm:text-lg max-w-2xl mx-auto mb-10 leading-relaxed"
          :style="{ color: 'var(--text-secondary)' }"
        >
          Deploy one-click de pipelines Medallion no Databricks, com um agente
          Claude autônomo que diagnostica falhas e abre PRs no GitHub enquanto você
          conversa com seus dados no chat.
        </p>

        <!-- CTAs com glow pulsante no primário -->
        <div class="flex items-center justify-center gap-3 mb-14">
          <span class="cta-glow">
            <AppButton size="lg" to="/register" trailing-icon="i-heroicons-arrow-right">
              Criar conta grátis
            </AppButton>
          </span>
          <AppButton variant="outline" size="lg" to="/login">
            Entrar
          </AppButton>
        </div>

        <!-- Platform preview card -->
        <div
          class="relative max-w-3xl mx-auto rounded-[var(--radius-2xl)] border overflow-hidden"
          :style="{
            borderColor: 'var(--border)',
            background: 'var(--surface)',
            boxShadow: 'var(--shadow-medium)',
          }"
        >
          <!-- Fake window chrome -->
          <div
            class="flex items-center gap-2 px-4 py-3 border-b"
            :style="{
              borderColor: 'var(--border)',
              background: 'var(--surface-elevated)',
            }"
          >
            <div class="flex gap-1.5">
              <span class="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
              <span class="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
              <span class="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
            </div>
            <div
              class="flex-1 mx-6 h-5 rounded-[var(--radius-sm)] flex items-center justify-center text-[10px] font-[var(--font-mono)]"
              :style="{ background: 'var(--bg)', color: 'var(--text-tertiary)' }"
            >
              app.safatechx.com/deployments/dep-5f9e2
            </div>
          </div>
          <!-- Fake content — saga steps preview -->
          <div class="p-6 space-y-2 text-left">
            <div
              v-for="step in previewSteps"
              :key="step.name"
              class="flex items-center gap-3 text-xs"
            >
              <div
                class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                :style="{ background: step.color }"
              >
                <AppIcon
                  v-if="step.done"
                  name="check"
                  size="xs"
                  class="text-white"
                />
                <span
                  v-else
                  class="w-1.5 h-1.5 rounded-full bg-white status-pulse"
                />
              </div>
              <span
                class="flex-1 font-[var(--font-mono)]"
                :style="{ color: 'var(--text-secondary)' }"
              >
                {{ step.name }}
              </span>
              <span
                class="tabular-nums"
                :style="{ color: 'var(--text-tertiary)' }"
              >
                {{ step.duration }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================ -->
    <!-- BENTO SHOWCASE — cards com visualizacoes reais do produto -->
    <!-- ============================================================ -->
    <section class="relative z-10">
      <!-- Breathing glow atras do header do bento -->
      <div
        class="breathing-glow"
        style="
          top: 40px;
          left: 50%;
          width: 900px;
          height: 500px;
          background: radial-gradient(ellipse at center, rgba(127, 34, 254, 0.22), transparent 55%);
        "
      />

      <div class="relative max-w-6xl mx-auto px-6 py-20">
        <div class="text-center mb-14">
          <p
            class="text-[10px] uppercase tracking-[0.22em] font-semibold mb-4"
            :style="{ color: 'var(--brand-500)' }"
          >
            Como funciona
          </p>
          <h2
            class="text-4xl sm:text-5xl mb-4 max-w-2xl mx-auto"
            :style="{
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-display)',
              fontWeight: 400,
              letterSpacing: '-0.02em',
              lineHeight: '1.05',
            }"
          >
            Quatro produtos.
            <span class="italic text-rainbow-purple">
              Um único fluxo.
            </span>
          </h2>
          <p
            class="text-sm sm:text-base max-w-xl mx-auto leading-relaxed"
            :style="{ color: 'var(--text-secondary)' }"
          >
            Cada card abaixo mostra exatamente o que você vai ver dentro
            da plataforma. Sem diagramas abstratos.
          </p>
        </div>

        <!-- Bento grid: 3 linhas × 3 colunas no desktop -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- ROW 1 — wide saga card (col-span-2) + observer timeline (col-span-1) -->
          <LandingSagaCard class="md:col-span-2" />
          <LandingObserverCard />

          <!-- ROW 2 — multichannel + code diff (col-span-2) -->
          <LandingMultichannelCard />
          <LandingCodeDiffCard class="md:col-span-2" />

          <!-- ROW 3 — metrics sparklines wide -->
          <LandingMetricsCard class="md:col-span-3" />

          <!-- ROW 4 — wide "more ways" card com grid de features extras -->
          <LandingMoreCard class="md:col-span-3" />
        </div>
      </div>
    </section>

    <!-- ============================================================ -->
    <!-- FINAL CTA estilo ngrok — 2 linhas horizontais + 4 brackets -->
    <!-- ============================================================ -->
    <section class="relative z-10 pt-24 pb-32">
      <!-- Breathing glow atras do final CTA -->
      <div
        class="breathing-glow"
        style="
          top: 50%;
          left: 50%;
          width: 800px;
          height: 500px;
          margin-top: -250px;
          background: radial-gradient(ellipse at center, rgba(127, 34, 254, 0.25), transparent 60%);
          animation-delay: 3s;
        "
      />

      <div class="final-cta-wrap relative max-w-3xl mx-auto px-6 py-20 text-center">
        <!-- Linha horizontal top — conecta os brackets TL e TR -->
        <div class="bracket-line bracket-line--top" />
        <!-- Linha horizontal bottom — conecta BL e BR -->
        <div class="bracket-line bracket-line--bottom" />

        <!-- 4 corner brackets (pequenos + nos cantos) -->
        <svg
          class="corner-bracket corner-bracket--tl"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          stroke-width="1.2"
        >
          <line x1="0" y1="10" x2="20" y2="10" />
          <line x1="10" y1="0" x2="10" y2="20" />
        </svg>
        <svg
          class="corner-bracket corner-bracket--tr"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          stroke-width="1.2"
        >
          <line x1="0" y1="10" x2="20" y2="10" />
          <line x1="10" y1="0" x2="10" y2="20" />
        </svg>
        <svg
          class="corner-bracket corner-bracket--bl"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          stroke-width="1.2"
        >
          <line x1="0" y1="10" x2="20" y2="10" />
          <line x1="10" y1="0" x2="10" y2="20" />
        </svg>
        <svg
          class="corner-bracket corner-bracket--br"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          stroke-width="1.2"
        >
          <line x1="0" y1="10" x2="20" y2="10" />
          <line x1="10" y1="0" x2="10" y2="20" />
        </svg>

        <h2
          class="text-4xl sm:text-5xl md:text-[56px] mb-5"
          :style="{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-display)',
            fontWeight: 400,
            letterSpacing: '-0.03em',
            lineHeight: '1.06',
          }"
        >
          Você leu a página inteira.
          <span class="block italic text-rainbow-purple">
            O que está esperando?
          </span>
        </h2>
        <p
          class="text-sm sm:text-base max-w-lg mx-auto mb-10"
          :style="{ color: 'var(--text-secondary)' }"
        >
          Sem custos iniciais.
          <span class="italic">Sem contato com vendas.</span>
          Pague apenas pelos runs que usar.
        </p>
        <div class="flex items-center justify-center gap-3 flex-wrap">
          <span class="cta-glow">
            <AppButton
              size="lg"
              to="/register"
              trailing-icon="i-heroicons-arrow-right"
            >
              Começar a construir
            </AppButton>
          </span>
          <AppButton
            size="lg"
            variant="outline"
            to="/marketplace"
          >
            Ver templates
          </AppButton>
        </div>
      </div>
    </section>

    <!-- ============================================================ -->
    <!-- FOOTER -->
    <!-- ============================================================ -->
    <footer
      class="relative z-10 border-t"
      :style="{ borderColor: 'var(--border)' }"
    >
      <div
        class="max-w-6xl mx-auto px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-3"
      >
        <p class="text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
          © 2026 Safatechx Labs · Plataforma agêntica de pipelines
        </p>
        <div class="flex items-center gap-4 text-[11px]">
          <a
            href="https://github.com/RodrigoSiliunas"
            target="_blank"
            rel="noopener"
            :style="{ color: 'var(--text-tertiary)' }"
          >
            GitHub
          </a>
          <NuxtLink to="/login" :style="{ color: 'var(--text-tertiary)' }">
            Entrar
          </NuxtLink>
          <NuxtLink to="/register" :style="{ color: 'var(--text-tertiary)' }">
            Criar conta
          </NuxtLink>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: "landing" })

const auth = useAuthStore()

// Apos hydration client-side (o plugin auth.client.ts ja leu o
// localStorage), se o user ja tem sessao valida, pula a landing e
// manda pro chat. Top-level await aqui seria executado no SSR com
// `isLoggedIn=false` (sem localStorage) e cacharia o resultado errado.
onMounted(() => {
  if (auth.isLoggedIn) {
    navigateTo("/chat", { replace: true })
  }
})

useHead({
  title: "Safatechx — Pipelines que corrigem a si mesmos",
  meta: [
    {
      name: "description",
      content:
        "Plataforma agêntica para pipelines Medallion no Databricks. Deploy one-click, diagnóstico autônomo via Claude, chat conversacional multi-canal.",
    },
  ],
})

interface PreviewStep {
  name: string
  done: boolean
  color: string
  duration: string
}

const previewSteps: PreviewStep[] = [
  { name: "Validate credentials", done: true, color: "var(--status-success)", duration: "2.2s" },
  { name: "Create AWS S3 bucket", done: true, color: "var(--status-success)", duration: "1.8s" },
  { name: "Provision IAM role", done: true, color: "var(--status-success)", duration: "1.2s" },
  { name: "Setup Unity Catalog", done: false, color: "var(--brand-600)", duration: "running..." },
  { name: "Upload notebooks", done: false, color: "var(--surface-elevated)", duration: "" },
  { name: "Create workflow", done: false, color: "var(--surface-elevated)", duration: "" },
]
</script>

<style scoped>
/* ----------------------------------------------------------------
 * Hero badge (estilo ngrok): label + separador + texto + arrow
 * ---------------------------------------------------------------- */
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.375rem 0.375rem 0.375rem 0.75rem;
  border-radius: 9999px;
  background: linear-gradient(
    135deg,
    rgba(127, 34, 254, 0.12) 0%,
    rgba(127, 34, 254, 0.04) 100%
  );
  border: 1px solid rgba(127, 34, 254, 0.25);
  box-shadow:
    0 0 0 1px rgba(127, 34, 254, 0.08),
    0 8px 32px -8px rgba(127, 34, 254, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  margin-bottom: 2rem;
  transition: all 0.3s ease;
  text-decoration: none;
}

.hero-badge:hover {
  border-color: rgba(127, 34, 254, 0.5);
  box-shadow:
    0 0 0 1px rgba(127, 34, 254, 0.2),
    0 12px 40px -8px rgba(127, 34, 254, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transform: translateY(-1px);
}

.hero-badge__label {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 0.2rem 0.55rem;
  border-radius: 9999px;
  background: linear-gradient(135deg, var(--brand-500), var(--brand-700));
  color: white;
  box-shadow: 0 2px 8px -2px rgba(127, 34, 254, 0.6);
}

.hero-badge__divider {
  display: inline-block;
  width: 1px;
  height: 12px;
  background: rgba(127, 34, 254, 0.3);
}

.hero-badge__text {
  font-size: 11px;
  font-weight: 500;
  color: var(--brand-300);
  letter-spacing: 0.01em;
}

.hero-badge__arrow {
  font-size: 12px;
  color: var(--brand-400);
  margin-right: 0.25rem;
}

/* ----------------------------------------------------------------
 * Final CTA — minimalista estilo ngrok: 2 linhas horizontais + 4 brackets
 * Sem box, sem border de fundo. So as linhas + corners + conteudo.
 * ---------------------------------------------------------------- */
.final-cta-wrap {
  position: relative;
}

/* Linhas horizontais atravessando o wrapper, com fade nas pontas */
.bracket-line {
  position: absolute;
  left: 10px;
  right: 10px;
  height: 1px;
  pointer-events: none;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(127, 34, 254, 0.35) 6%,
    rgba(127, 34, 254, 0.35) 94%,
    transparent 100%
  );
}

.bracket-line--top {
  top: 0;
}

.bracket-line--bottom {
  bottom: 0;
}

/* Corner brackets — "+" pequeno centralizado no canto da linha horizontal */
.corner-bracket {
  position: absolute;
  width: 20px;
  height: 20px;
  color: rgba(127, 34, 254, 0.65);
  pointer-events: none;
  z-index: 2;
}

.corner-bracket--tl {
  top: -10px;
  left: -10px;
}

.corner-bracket--tr {
  top: -10px;
  right: -10px;
}

.corner-bracket--bl {
  bottom: -10px;
  left: -10px;
}

.corner-bracket--br {
  bottom: -10px;
  right: -10px;
}
</style>
