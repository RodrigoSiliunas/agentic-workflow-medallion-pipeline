<template>
  <LandingCardShell
    eyebrow="PR automático"
    title="O fix vem pronto. Você só revisa."
    description="Cada diagnóstico vira um PR no GitHub com diff testado via ruff e validado antes de abrir."
  >
    <div
      class="mx-6 mb-6 rounded-[var(--radius-md)] border overflow-hidden"
      :style="{ borderColor: 'var(--border)', background: 'var(--bg)' }"
    >
      <!-- Editor-style header -->
      <div
        class="flex items-center justify-between px-3 py-2 border-b"
        :style="{ borderColor: 'var(--border)', background: 'var(--surface-elevated)' }"
      >
        <div class="flex items-center gap-2 min-w-0">
          <svg viewBox="0 0 16 16" class="w-3 h-3 flex-shrink-0" :style="{ color: 'var(--text-tertiary)' }">
            <path fill="currentColor" d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z"/>
          </svg>
          <span class="text-[10px] font-[var(--font-mono)] truncate" :style="{ color: 'var(--text-secondary)' }">
            fix/agent-auto-bronze-oom
          </span>
          <span class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">·</span>
          <span class="text-[10px] font-[var(--font-mono)] truncate" :style="{ color: 'var(--text-tertiary)' }">
            pipeline_lib/storage/s3_client.py
          </span>
        </div>
        <div class="flex items-center gap-1.5 flex-shrink-0">
          <span
            class="inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-sm font-medium"
            :style="{ background: 'rgba(16, 185, 129, 0.15)', color: 'var(--status-success)' }"
          >
            ✓ ruff passed
          </span>
          <span
            class="inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-sm font-medium"
            :style="{ background: 'rgba(127, 34, 254, 0.15)', color: 'var(--brand-400)' }"
          >
            PR #15
          </span>
        </div>
      </div>

      <!-- Diff body -->
      <div class="p-3 font-[var(--font-mono)] text-[11px] leading-[1.55] overflow-x-auto">
        <div
          v-for="(line, idx) in diffLines"
          :key="idx"
          class="flex"
          :style="{ background: rowBg(line.kind) }"
        >
          <span
            class="inline-block w-7 flex-shrink-0 text-right pr-2 tabular-nums select-none"
            :style="{ color: 'var(--text-tertiary)' }"
          >{{ line.lineNo }}</span>
          <span
            class="inline-block w-4 flex-shrink-0 text-center select-none"
            :style="{ color: gutterColor(line.kind) }"
          >{{ gutterChar(line.kind) }}</span>
          <span
            class="flex-1 whitespace-pre"
            :style="{ color: textColor(line.kind) }"
          >
            <span
              v-for="(tok, i) in tokenize(line.text)"
              :key="i"
              :style="{ color: tok.color }"
            >{{ tok.text }}</span>
          </span>
        </div>
      </div>

      <!-- Footer stats -->
      <div
        class="flex items-center justify-between px-3 py-2 border-t text-[10px]"
        :style="{ borderColor: 'var(--border)', background: 'var(--surface-elevated)' }"
      >
        <div class="flex items-center gap-3">
          <span class="flex items-center gap-1">
            <span class="inline-block w-2 h-2 rounded-sm" :style="{ background: 'rgba(16, 185, 129, 0.5)' }" />
            <span :style="{ color: 'var(--text-tertiary)' }">+3 adições</span>
          </span>
          <span class="flex items-center gap-1">
            <span class="inline-block w-2 h-2 rounded-sm" :style="{ background: 'rgba(239, 68, 68, 0.5)' }" />
            <span :style="{ color: 'var(--text-tertiary)' }">−4 remoções</span>
          </span>
        </div>
        <span :style="{ color: 'var(--text-tertiary)' }">
          confiança
          <span class="tabular-nums font-medium" :style="{ color: 'var(--brand-400)' }">94%</span>
        </span>
      </div>
    </div>
  </LandingCardShell>
</template>

<script setup lang="ts">
type LineKind = "ctx" | "add" | "del"

interface DiffLine {
  lineNo: string
  kind: LineKind
  text: string
}

const diffLines: DiffLine[] = [
  { lineNo: "142", kind: "ctx", text: "def read_parquet(self, prefix: str) -> DataFrame:" },
  { lineNo: "143", kind: "ctx", text: '    """Read Parquet from S3 to Spark DataFrame."""' },
  { lineNo: "144", kind: "del", text: "    import boto3" },
  { lineNo: "145", kind: "del", text: "    import pandas as pd" },
  { lineNo: "146", kind: "del", text: "    s3 = boto3.client('s3')" },
  { lineNo: "147", kind: "del", text: "    df = pd.read_parquet(f's3://{bucket}/{prefix}')" },
  { lineNo: "146", kind: "add", text: "    bucket = self.config['s3_bucket']" },
  { lineNo: "147", kind: "add", text: "    path = f's3a://{bucket}/{prefix}'" },
  { lineNo: "148", kind: "add", text: "    return spark.read.parquet(path)" },
  { lineNo: "149", kind: "ctx", text: "" },
]

function rowBg(kind: LineKind): string {
  if (kind === "add") return "rgba(16, 185, 129, 0.08)"
  if (kind === "del") return "rgba(239, 68, 68, 0.08)"
  return "transparent"
}

function gutterColor(kind: LineKind): string {
  if (kind === "add") return "var(--status-success)"
  if (kind === "del") return "var(--status-error)"
  return "var(--text-tertiary)"
}

function gutterChar(kind: LineKind): string {
  if (kind === "add") return "+"
  if (kind === "del") return "−"
  return " "
}

function textColor(kind: LineKind): string {
  return kind === "ctx" ? "var(--text-secondary)" : "var(--text-primary)"
}

// Tokenizer simples para python — retorna array de { text, color }
// pra renderizar como <span> em v-for, sem v-html.
interface Token {
  text: string
  color: string
}

const KEYWORDS = new Set([
  "def",
  "return",
  "import",
  "from",
  "as",
  "if",
  "else",
  "for",
  "in",
  "self",
  "class",
])

const COLOR_DEFAULT = "inherit"
const COLOR_STRING = "#10b981"
const COLOR_KEYWORD = "#a78bfa"
const COLOR_FUNCTION = "#60a5fa"

function tokenize(raw: string): Token[] {
  if (!raw) return [{ text: "", color: COLOR_DEFAULT }]

  const tokens: Token[] = []
  // Regex unica com alternativas: string | keyword | function call | non-word | identifier
  const pattern =
    /("[^"]*"|'[^']*')|(\b[a-zA-Z_][a-zA-Z0-9_]*\b)(?=\()|([a-zA-Z_][a-zA-Z0-9_]*)|([^\w"']+)/g

  let lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(raw)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ text: raw.slice(lastIndex, match.index), color: COLOR_DEFAULT })
    }
    const [full, str, fnCall, ident, punct] = match
    if (str !== undefined) {
      tokens.push({ text: str, color: COLOR_STRING })
    } else if (fnCall !== undefined) {
      if (KEYWORDS.has(fnCall)) {
        tokens.push({ text: fnCall, color: COLOR_KEYWORD })
      } else {
        tokens.push({ text: fnCall, color: COLOR_FUNCTION })
      }
    } else if (ident !== undefined) {
      if (KEYWORDS.has(ident)) {
        tokens.push({ text: ident, color: COLOR_KEYWORD })
      } else {
        tokens.push({ text: ident, color: COLOR_DEFAULT })
      }
    } else if (punct !== undefined) {
      tokens.push({ text: punct, color: COLOR_DEFAULT })
    } else {
      tokens.push({ text: full, color: COLOR_DEFAULT })
    }
    lastIndex = match.index + full.length
  }
  if (lastIndex < raw.length) {
    tokens.push({ text: raw.slice(lastIndex), color: COLOR_DEFAULT })
  }
  return tokens
}
</script>
