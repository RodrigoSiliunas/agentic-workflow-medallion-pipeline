"""Interfaces base para providers do Observer Agent.

Define os contratos que LLM e Git providers devem implementar.
Novos providers são adicionados implementando estas ABCs e registrando
no factory via decorator @register_llm_provider / @register_git_provider.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)


def with_retry(max_retries: int = 3, base_delay: float = 2.0):
    """Decorator: retry com exponential backoff para chamadas externas.

    Retenta em exceções transientes (rede, rate limit, timeout).
    Não retenta em erros de lógica (ValueError, KeyError, etc).
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ValueError, KeyError, TypeError, ImportError):
                    raise  # Erros de lógica — não retenta
                except Exception as e:
                    last_error = e
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"Tentativa {attempt + 1}/{max_retries} falhou: {e}. "
                        f"Retentando em {delay:.0f}s..."
                    )
                    time.sleep(delay)
            raise last_error  # type: ignore[misc]
        return wrapper
    return decorator


@dataclass
class DiagnosisResult:
    """Resultado padronizado de um diagnóstico LLM.

    Todos os providers retornam este objeto independente do modelo usado.
    """

    diagnosis: str = ""
    root_cause: str = ""
    fix_description: str = ""
    fixed_code: str | None = None
    file_to_fix: str | None = None
    confidence: float = 0.0
    requires_human_review: bool = True
    additional_notes: str = ""

    # Metadata do provider (preenchido automaticamente)
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "diagnosis": self.diagnosis,
            "root_cause": self.root_cause,
            "fix_description": self.fix_description,
            "fixed_code": self.fixed_code,
            "file_to_fix": self.file_to_fix,
            "confidence": self.confidence,
            "requires_human_review": self.requires_human_review,
            "additional_notes": self.additional_notes,
            "_provider": self.provider,
            "_model": self.model,
            "_input_tokens": self.input_tokens,
            "_output_tokens": self.output_tokens,
        }


@dataclass
class DiagnosisRequest:
    """Contexto completo enviado ao LLM para diagnóstico."""

    error_message: str
    stack_trace: str
    failed_task: str
    notebook_code: str
    schema_info: str
    pipeline_state: dict = field(default_factory=dict)


@dataclass
class PRResult:
    """Resultado padronizado da criação de um PR."""

    pr_url: str
    pr_number: int
    branch_name: str

    def to_dict(self) -> dict:
        return {
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "branch_name": self.branch_name,
        }


class LLMProvider(ABC):
    """Interface para providers de LLM (Anthropic, OpenAI, Ollama, etc).

    Cada provider implementa diagnose() que recebe um DiagnosisRequest
    e retorna um DiagnosisResult padronizado.
    """

    @abstractmethod
    def diagnose(self, request: DiagnosisRequest) -> DiagnosisResult:
        """Envia contexto ao LLM e retorna diagnóstico estruturado."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome do provider (ex: 'anthropic', 'openai')."""
        ...


class GitProvider(ABC):
    """Interface para providers de Git (GitHub, GitLab, Bitbucket, etc).

    Cada provider implementa create_fix_pr() que cria branch + PR.
    get_pr_status() eh opcional — subclasses podem sobrescrever para
    suportar a logica de deduplicacao baseada em status de PRs existentes.
    """

    @abstractmethod
    def create_fix_pr(
        self,
        diagnosis: DiagnosisResult,
        failed_task: str,
    ) -> PRResult:
        """Cria branch com fix e abre PR."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome do provider (ex: 'github', 'gitlab')."""
        ...

    def get_pr_status(self, pr_number: int) -> str:
        """Retorna o status de um PR: 'open', 'merged', 'closed' ou 'unknown'.

        Implementacao default retorna 'unknown'. Providers que suportam
        consulta de status (como GitHub) devem sobrescrever este metodo.
        Eh usado pela logica de deduplicacao para decidir se deve pular
        diagnosticos duplicados (PR open/merged) ou permitir re-diagnostico
        (PR closed sem merge).
        """
        return "unknown"
