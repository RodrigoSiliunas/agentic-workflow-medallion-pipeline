/**
 * useSafeMarkdown — renderer markdown com sanitização de URLs (T2 Phase 2).
 *
 * Contexto: o chat injeta texto vindo de LLM/Omni como HTML via `v-html`.
 * Sem sanitização de scheme, um payload como `[click](javascript:alert(1))`
 * vira um link clicável que executa script — suficiente para roubar o
 * access token (pre-T2) ou para phishing via links disfarçados.
 *
 * Estratégia:
 * 1. Escape HTML genérico (já existia). Mantém entidades seguras.
 * 2. Regex markdown tradicional (headers, bold, listas, tabelas, código).
 * 3. Links passam por `isSafeUrl()`: allowlist de schemes
 *    (`http`, `https`, `mailto`, `tel`, anchors, relativos). URL hostil
 *    é descartada — renderiza só o label escapado.
 *
 * O `escapeHtml` é exportado para uso nos testes e para quem precisar
 * reusar fora do markdown renderer.
 */

const SAFE_SCHEME = /^(https?:|mailto:|tel:|#|\/|\.\.?\/)/i

export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

/**
 * True se `url` usa um scheme permitido OU é relativo (sem `:`).
 *
 * Rejeita explicitamente: `javascript:`, `data:`, `vbscript:`, `file:`,
 * `blob:`, `about:`, e qualquer scheme arbitrário não listado.
 */
export function isSafeUrl(url: string): boolean {
  if (!url) return false
  const trimmed = url.trim()
  if (!trimmed) return false
  // Caracteres de controle/whitespace dentro da URL são um smell
  // clássico de bypass (ex: `java\tscript:...`).
  if (/[\x00-\x1f\x7f]/.test(trimmed)) return false

  if (SAFE_SCHEME.test(trimmed)) return true

  // Sem `:` = relativo (`path/to`, `foo.html`, `page?q=1`)
  if (!trimmed.includes(":")) return true

  return false
}

export function renderMarkdown(input: string): string {
  let text = escapeHtml(input)

  // Code blocks (antes de inline pra nao conflitar)
  text = text.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    '<pre class="bg-[var(--surface-elevated)] border border-[var(--border)] p-3 rounded-[var(--radius-md)] overflow-x-auto my-2 text-xs"><code>$2</code></pre>',
  )
  // Inline code
  text = text.replace(
    /`([^`]+)`/g,
    '<code class="bg-[var(--surface-elevated)] border border-[var(--border)] px-1 py-0.5 rounded text-[11px]">$1</code>',
  )
  // Headers (#### → h5, ### → h4, ## → h3)
  text = text.replace(
    /^#{4,} (.+)$/gm,
    '<h5 class="text-xs font-semibold mt-3 mb-1" style="color: var(--text-primary)">$1</h5>',
  )
  text = text.replace(
    /^### (.+)$/gm,
    '<h4 class="text-sm font-semibold mt-3 mb-1" style="color: var(--text-primary)">$1</h4>',
  )
  text = text.replace(
    /^## (.+)$/gm,
    '<h3 class="text-base font-semibold mt-3 mb-1" style="color: var(--text-primary)">$1</h3>',
  )
  // Horizontal rule (---)
  text = text.replace(
    /^-{3,}$/gm,
    '<hr class="border-t border-[var(--border)] my-3" />',
  )
  // Bold
  text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
  // Italic (single *)
  text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>")
  // Links — scheme allowlist
  text = text.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (_match, label: string, href: string) => {
      if (!isSafeUrl(href)) {
        // URL hostil — renderiza só o label. O label já vem escapado.
        return label
      }
      // href vem do texto escapado, então aspas/`<` já estão neutras;
      // ainda assim re-escape explicitamente para barrar edge cases.
      const safeHref = escapeHtml(href)
      return (
        `<a href="${safeHref}" target="_blank" rel="noopener noreferrer" ` +
        `class="underline text-[var(--brand-500)]">${label}</a>`
      )
    },
  )
  // Tables (| col1 | col2 | ... |)
  text = text.replace(
    /^(\|.+\|)\n\|[-| :]+\|\n((?:\|.+\|\n?)+)/gm,
    (_match, header: string, body: string) => {
      const ths = header
        .split("|")
        .filter(Boolean)
        .map(
          (c: string) =>
            `<th class="px-2 py-1 text-left text-[10px] font-semibold" style="color:var(--text-tertiary)">${c.trim()}</th>`,
        )
        .join("")
      const rows = body
        .trim()
        .split("\n")
        .map((row: string) => {
          const tds = row
            .split("|")
            .filter(Boolean)
            .map(
              (c: string) =>
                `<td class="px-2 py-1 text-[11px] border-t border-[var(--border)]">${c.trim()}</td>`,
            )
            .join("")
          return `<tr>${tds}</tr>`
        })
        .join("")
      return (
        `<table class="w-full border border-[var(--border)] rounded-[var(--radius-md)] overflow-hidden my-2">` +
        `<thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table>`
      )
    },
  )
  // Lists (- item)
  text = text.replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
  // Numbered lists (1. item)
  text = text.replace(
    /^\d+\. (.+)$/gm,
    '<li class="ml-4 list-decimal">$1</li>',
  )

  return text
}
