/**
 * Mock data para threads — usado pelo composable useChatApi
 * quando mockMode esta ativo.
 */
import type { ChatMessage, Thread } from "~/types/chat"

export interface ThreadWithMessages extends Thread {
  messages: ChatMessage[]
}

const DEFAULT_PIPELINE_ID = "medallion_pipeline_whatsapp"

function relative(daysAgo: number): string {
  const d = new Date()
  d.setDate(d.getDate() - daysAgo)
  d.setHours(d.getHours() - Math.floor(Math.random() * 8))
  return d.toISOString()
}

export const MOCK_THREADS: ThreadWithMessages[] = [
  {
    id: "t-001",
    pipelineId: DEFAULT_PIPELINE_ID,
    title: "Por que o bronze falhou hoje?",
    lastActivity: relative(0),
    messageCount: 4,
    channel: "web",
    messages: [
      {
        id: "m-001-1",
        role: "user",
        content: "Por que o bronze_ingestion falhou hoje de manha?",
        channel: "web",
        timestamp: relative(0),
      },
      {
        id: "m-001-2",
        role: "assistant",
        content:
          "O `bronze_ingestion` teve `OutOfMemoryError: GC overhead limit exceeded` no driver as 14:32. Causa raiz: `S3Lake.read_parquet` materializava 153k linhas via boto3 + pandas no driver. O Observer Agent diagnosticou e abriu o **PR #15** com fix usando `spark.read.parquet(s3a://...)` nativo.",
        channel: "web",
        timestamp: relative(0),
        actions: [
          {
            type: "pr_created",
            status: "success",
            details: { number: 15, url: "https://github.com/RodrigoSiliunas/observer/pull/15" },
          },
        ],
      },
      {
        id: "m-001-3",
        role: "user",
        content: "Beleza, ja mergei. O pipeline rodou de novo?",
        channel: "web",
        timestamp: relative(0),
      },
      {
        id: "m-001-4",
        role: "assistant",
        content:
          "Sim — o run `826862455884866` completou com SUCCESS as 15:18. `bronze_ingestion` rodou em 125.9s (antes batia OOM em 3+ retries). Tabela `medallion.bronze.conversations` tem 153.228 linhas.",
        channel: "web",
        timestamp: relative(0),
      },
    ],
  },
  {
    id: "t-002",
    pipelineId: DEFAULT_PIPELINE_ID,
    title: "Schema warning na silver",
    lastActivity: relative(1),
    messageCount: 2,
    channel: "web",
    messages: [
      {
        id: "m-002-1",
        role: "user",
        content: "Apareceu um warning de schema na silver/dedup. Eh problema?",
        channel: "web",
        timestamp: relative(1),
      },
      {
        id: "m-002-2",
        role: "assistant",
        content:
          "Nao eh problema. O Delta Lake aceita colunas novas via `mergeSchema`. O warning indica que duas colunas extras (`agent_notes`, `priority_tier`) foram adicionadas a partir do bronze. Elas vao propagar pra silver e gold automaticamente. Se quiser tipar elas, atualize `pipeline_lib/schema/contracts.py`.",
        channel: "web",
        timestamp: relative(1),
      },
    ],
  },
  {
    id: "t-003",
    pipelineId: DEFAULT_PIPELINE_ID,
    title: "Multi-file PR #14",
    lastActivity: relative(3),
    messageCount: 3,
    channel: "web",
    messages: [
      {
        id: "m-003-1",
        role: "user",
        content: "O Observer abriu um PR com 2 arquivos modificados. Foi proposital?",
        channel: "web",
        timestamp: relative(3),
      },
      {
        id: "m-003-2",
        role: "assistant",
        content:
          "Sim. O bug cruzava modulos: `pipeline_lib/schema/contracts.py` precisava de uma coluna nova e `notebooks/silver/dedup_clean.py` precisava usar essa coluna no group by. O Observer detectou via prompt que era multi-file e usou o campo `fixes` no `DiagnosisResult` em vez do `fixed_code` singular.",
        channel: "web",
        timestamp: relative(3),
      },
      {
        id: "m-003-3",
        role: "assistant",
        content: "Validacao pre-PR rodou ruff em ambos os arquivos antes de criar o PR.",
        channel: "web",
        timestamp: relative(3),
      },
    ],
  },
  {
    id: "t-004",
    pipelineId: DEFAULT_PIPELINE_ID,
    title: "Dedup activated — economia de tokens",
    lastActivity: relative(5),
    messageCount: 2,
    channel: "web",
    messages: [
      {
        id: "m-004-1",
        role: "user",
        content: "Quanto a feature de dedup esta economizando?",
        channel: "web",
        timestamp: relative(5),
      },
      {
        id: "m-004-2",
        role: "assistant",
        content:
          "Nos ultimos 30 dias, **18 cache hits** evitaram chamadas duplicadas ao Claude Opus. Estimativa de economia: ~$3.40 em tokens. Mais importante: zero PRs duplicados barulhentos no GitHub.",
        channel: "web",
        timestamp: relative(5),
      },
    ],
  },
  {
    id: "t-005",
    pipelineId: DEFAULT_PIPELINE_ID,
    title: "Custos do Observer este mes",
    lastActivity: relative(12),
    messageCount: 2,
    channel: "web",
    messages: [
      {
        id: "m-005-1",
        role: "user",
        content: "Qual o custo total do Observer no mes?",
        channel: "web",
        timestamp: relative(12),
      },
      {
        id: "m-005-2",
        role: "assistant",
        content:
          "**$4.82** em tokens Claude Opus + $0.00 em GitHub API. Total de **23 diagnosticos** persistidos em `medallion.observer.diagnostics`, sendo 19 com PR criado, 3 dedup skip, 1 dry-run.",
        channel: "web",
        timestamp: relative(12),
      },
    ],
  },
]

/**
 * Gera uma resposta mock baseada em palavras-chave do input. Simples
 * heuristica para os mocks parecerem contextuais ate o backend chegar.
 */
export function mockReplyFor(input: string): string {
  const lower = input.toLowerCase()
  if (lower.includes("erro") || lower.includes("falha")) {
    return "Verificando os ultimos runs do `medallion_pipeline_whatsapp`... O ultimo run completou com SUCCESS. Se voce viu uma falha especifica, me passe o run_id que eu olho com mais detalhe na tabela `observer.diagnostics`."
  }
  if (lower.includes("custo") || lower.includes("token")) {
    return "Nos ultimos 30 dias o Observer gastou ~$4.82 em tokens Claude Opus. Total de 23 diagnosticos persistidos. Quer que eu abra o painel SQL com o breakdown por dia?"
  }
  if (lower.includes("status") || lower.includes("health")) {
    return "O pipeline `medallion_pipeline_whatsapp` esta **active**. Ultimo run: SUCCESS as 15:18 (run_id 826862455884866). Bronze 125.9s, silver+gold completos, validation OK. observer_trigger ficou EXCLUDED (sem falhas)."
  }
  if (lower.includes("pr") || lower.includes("github")) {
    return "Os PRs do Observer aparecem em `RodrigoSiliunas/agentic-workflow-medallion-pipeline` na branch `dev`, prefixados com `fix/agent-auto-*`. Quer que eu liste os abertos atualmente?"
  }
  return "Posso te ajudar a investigar runs, custos, PRs do Observer, ou qualquer aspecto do pipeline `medallion_pipeline_whatsapp`. O que voce quer saber?"
}
