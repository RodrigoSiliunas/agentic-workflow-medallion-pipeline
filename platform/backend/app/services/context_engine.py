"""Context Engine — monta prompt com contexto do pipeline para o LLM.

3 niveis de contexto:
- Nivel 1 (resumo): ~800 tokens — status, ultima run, metricas basicas
- Nivel 2 (detalhes): ~8k tokens — schemas, historico de runs, erros recentes
- Nivel 3 (completo): ~35k tokens — codigo de notebooks, logs detalhados
"""

import json
import uuid
from dataclasses import dataclass, field

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.databricks_service import DatabricksService
from app.services.github_service import GitHubService

logger = structlog.get_logger()

# Budget de tokens
MAX_CONTEXT_TOKENS = 80_000
RESERVED_CONVERSATION = 15_000
RESERVED_SYSTEM = 3_000


@dataclass
class ContextBlock:
    type: str
    content: str
    token_estimate: int
    priority: int  # 1-10, 10 = maxima


@dataclass
class AssembledContext:
    system_prompt: str
    blocks: list[ContextBlock] = field(default_factory=list)
    total_tokens: int = 0


SYSTEM_PROMPT = """Voce e o assistente do pipeline Medallion da empresa no Safatechx Platform.
Voce tem acesso a tools que consultam Databricks e GitHub em tempo real.

REGRAS CRITICAS:
- Responda SEMPRE em portugues brasileiro (pt-BR)
- USE AS TOOLS PROATIVAMENTE. Quando o usuario perguntar algo, CHAME a tool
  relevante ANTES de responder. NAO pergunte "quer que eu verifique?" — va direto.
  Exemplo: "qual o status?" → chame get_pipeline_status IMEDIATAMENTE.
  Exemplo: "qual a ultima correcao?" → chame list_recent_prs IMEDIATAMENTE.
  Exemplo: "quantas tabelas gold?" → chame get_table_schema IMEDIATAMENTE.
- Para acoes destrutivas (trigger_run, create_pr), peca confirmacao ANTES
- Use dados reais retornados pelas tools, nunca invente
- Respostas concisas e diretas — nao repita o que o usuario ja sabe
- Formate com markdown (negrito, listas, headers) pra facilitar leitura
- Se uma tool falhar, tente outra abordagem (ex: se get_pipeline_status falhar
  com job_id=0, tente com o job_id do contexto)

TOOLS DISPONIVEIS:
- get_pipeline_status: status, ultima run, duracao
- get_run_logs: logs detalhados de uma run especifica
- query_delta_table: SELECT SQL em tabelas Delta (bronze/silver/gold)
- get_table_schema: lista todas as tabelas e colunas
- read_file: le arquivo do repo (path relativo, ex: "pipelines/.../notebooks/bronze/ingest.py")
- list_recent_prs: PRs recentes (inclui correcoes automaticas do Observer)
- get_pr_diff: mostra o diff de um PR especifico (arquivos alterados + patch)
- create_pull_request: cria PR com mudancas (pede confirmacao)
- trigger_pipeline_run: dispara execucao (pede confirmacao)

FLUXO RECOMENDADO para perguntas sobre correcoes:
1. list_recent_prs → encontra o PR relevante
2. get_pr_diff(pr_number) → mostra o que mudou (patch com +/- lines)
3. Explica em linguagem humana o que foi corrigido
"""

# Intent classification por keywords
INTENT_KEYWORDS = {
    "status_check": ["status", "como esta", "rodou", "execucao", "run", "ultimo", "proximo"],
    "error_diagnosis": ["erro", "falhou", "falha", "problema", "bug", "quebrou", "por que"],
    "change_request": ["adicionar", "criar", "nova tabela", "modificar", "mudar", "alterar"],
    "report_request": ["relatorio", "metricas", "conversao", "dashboard", "quantos", "quantas"],
    "fix_request": [
        "corrigir", "fix", "arrumar", "ajustar", "regex", "conserta",
        "correcao", "correção", "pr", "pull request", "observer",
        "automatica", "automatico", "agente", "codigo", "código",
    ],
}

# Prioridades por intent
INTENT_PRIORITIES = {
    "status_check": {"pipeline_state": 10, "run_history": 8, "table_schemas": 4},
    "error_diagnosis": {
        "pipeline_state": 10, "recent_errors": 10, "notebook_code": 8, "table_schemas": 6,
    },
    "change_request": {"table_schemas": 9, "notebook_code": 8, "recent_prs": 6},
    "report_request": {"pipeline_state": 8, "table_schemas": 7, "run_history": 6},
    "fix_request": {"recent_errors": 10, "notebook_code": 9, "table_schemas": 7},
    "general": {"pipeline_state": 8, "table_schemas": 5, "run_history": 4},
}


def classify_intent(message: str) -> str:
    """Classifica a intencao do usuario por keywords."""
    message_lower = message.lower()
    scores: dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in message_lower)
        if score > 0:
            scores[intent] = score

    if not scores:
        return "general"
    return max(scores, key=scores.get)


def estimate_tokens(text: str) -> int:
    """Estimativa rapida de tokens (~4 chars/token para pt-BR)."""
    return len(text) // 4


class ContextEngine:
    def __init__(self, db: AsyncSession, company_id: uuid.UUID):
        self.db = db
        self.company_id = company_id
        self.databricks = DatabricksService(db, company_id)
        self.github = GitHubService(db, company_id)

    async def assemble(
        self, pipeline_job_id: int, user_message: str, detail_level: int = 0
    ) -> AssembledContext:
        """Monta contexto para o LLM.

        detail_level: 0=auto (classifica intent), 1=resumo, 2=detalhes, 3=completo
        """
        intent = classify_intent(user_message)
        if detail_level == 0:
            # Auto-select baseado no intent
            level_map = {"error_diagnosis": 3, "fix_request": 3, "change_request": 2}
            detail_level = level_map.get(intent, 1)

        logger.info("Context assembly", intent=intent, detail_level=detail_level)

        priorities = INTENT_PRIORITIES.get(intent, INTENT_PRIORITIES["general"])
        available = MAX_CONTEXT_TOKENS - RESERVED_CONVERSATION - RESERVED_SYSTEM

        blocks: list[ContextBlock] = []

        # Nivel 1: Resumo (sempre incluso)
        try:
            summary = await self.databricks.get_pipeline_summary(pipeline_job_id)
            block_text = f"Pipeline Status: {json.dumps(summary, indent=2, default=str)}"
            blocks.append(ContextBlock(
                type="pipeline_state",
                content=block_text,
                token_estimate=estimate_tokens(block_text),
                priority=priorities.get("pipeline_state", 5),
            ))
        except Exception as e:
            logger.warning("Falha ao obter pipeline summary", error=str(e))

        # Nivel 2: Detalhes (se detail_level >= 2)
        if detail_level >= 2:
            try:
                schemas = await self.databricks.get_table_schemas()
                block_text = f"Table Schemas:\n{json.dumps(schemas, indent=2)}"
                blocks.append(ContextBlock(
                    type="table_schemas",
                    content=block_text,
                    token_estimate=estimate_tokens(block_text),
                    priority=priorities.get("table_schemas", 5),
                ))
            except Exception as e:
                logger.warning("Falha ao obter schemas", error=str(e))

            try:
                runs = await self.databricks.list_runs(pipeline_job_id, limit=5)
                block_text = f"Run History (last 5):\n{json.dumps(runs, indent=2, default=str)}"
                blocks.append(ContextBlock(
                    type="run_history",
                    content=block_text,
                    token_estimate=estimate_tokens(block_text),
                    priority=priorities.get("run_history", 4),
                ))
            except Exception as e:
                logger.warning("Falha ao obter historico de runs", error=str(e))

            try:
                prs = await self.github.list_recent_prs(limit=5)
                block_text = f"Recent PRs:\n{json.dumps(prs, indent=2)}"
                blocks.append(ContextBlock(
                    type="recent_prs",
                    content=block_text,
                    token_estimate=estimate_tokens(block_text),
                    priority=priorities.get("recent_prs", 3),
                ))
            except Exception:
                pass

        # Nivel 3: Completo (se detail_level >= 3)
        if detail_level >= 3:
            # Ler codigo de notebooks relevantes ao intent
            relevant_notebooks = self._select_relevant_notebooks(intent)
            for nb_path in relevant_notebooks:
                try:
                    code = await self.github.read_file(nb_path)
                    block_text = f"Notebook {nb_path}:\n```python\n{code}\n```"
                    blocks.append(ContextBlock(
                        type="notebook_code",
                        content=block_text,
                        token_estimate=estimate_tokens(block_text),
                        priority=priorities.get("notebook_code", 4),
                    ))
                except Exception:
                    pass

        # Ranquear e cortar pelo budget
        blocks.sort(key=lambda b: b.priority, reverse=True)

        selected: list[ContextBlock] = []
        tokens_used = 0
        for block in blocks:
            if tokens_used + block.token_estimate <= available:
                selected.append(block)
                tokens_used += block.token_estimate

        return AssembledContext(
            system_prompt=SYSTEM_PROMPT,
            blocks=selected,
            total_tokens=tokens_used + RESERVED_SYSTEM,
        )

    def _select_relevant_notebooks(self, intent: str) -> list[str]:
        """Seleciona notebooks relevantes ao intent."""
        base = "pipeline/notebooks/"
        if intent in ("error_diagnosis", "fix_request"):
            return [
                f"{base}agent_post.py",
                f"{base}silver/dedup_clean.py",
                f"{base}silver/entities_mask.py",
                f"{base}validation/checks.py",
            ]
        if intent == "change_request":
            return [
                f"{base}gold/analytics.py",
                f"{base}silver/enrichment.py",
            ]
        return [f"{base}agent_pre.py"]
