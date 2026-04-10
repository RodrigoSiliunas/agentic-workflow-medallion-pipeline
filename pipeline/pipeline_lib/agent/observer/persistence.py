"""Persistencia de diagnosticos do Observer em Delta Table.

Registra cada diagnostico (sucesso ou falha) na tabela `{catalog}.observer.diagnostics`
para observabilidade, metricas de custo e deduplicacao futura.

Uso:
    from pipeline_lib.agent.observer.persistence import ObserverDiagnosticsStore

    store = ObserverDiagnosticsStore(spark, catalog="medallion")
    store.ensure_schema()
    record = store.build_record(
        diagnosis=diagnosis_result,
        pr_result=pr_result,
        job_id=123,
        job_name="medallion_pipeline_whatsapp",
        run_id=456,
        failed_task="bronze_ingestion",
        error_message="...",
        duration_seconds=12.3,
        status="success",
    )
    store.save(record)
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Precos publicos por 1M tokens (input, output) em USD
# Atualizado em 2026-04-10. Fonte: paginas oficiais dos providers.
PRICING: dict[tuple[str, str], tuple[float, float]] = {
    ("anthropic", "claude-opus"): (15.0, 75.0),
    ("anthropic", "claude-sonnet"): (3.0, 15.0),
    ("anthropic", "claude-haiku"): (0.80, 4.0),
    ("openai", "gpt-4o"): (2.50, 10.0),
    ("openai", "gpt-4-turbo"): (10.0, 30.0),
    ("openai", "gpt-4"): (30.0, 60.0),
    ("openai", "gpt-3.5-turbo"): (0.50, 1.50),
}


def calculate_cost_usd(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Calcula custo estimado em USD a partir de provider, modelo e tokens.

    Busca a tabela PRICING pelo prefixo do modelo (ex: 'claude-opus-4-20250514'
    casa com 'claude-opus'). Retorna 0.0 se o provider/modelo for desconhecido.
    """
    provider_norm = (provider or "").strip().lower()
    model_norm = (model or "").strip().lower()

    for (prov, model_prefix), (in_price, out_price) in PRICING.items():
        if prov == provider_norm and model_norm.startswith(model_prefix):
            # PRICING eh por 1M tokens — dividimos por 1_000_000
            return round(
                (input_tokens * in_price + output_tokens * out_price) / 1_000_000,
                6,
            )

    return 0.0


def error_hash(error_message: str) -> str:
    """Gera hash SHA-256 do error_message para deduplicacao de diagnosticos.

    Normaliza a mensagem (strip) para que whitespace nao afete o hash.
    """
    normalized = (error_message or "").strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


@dataclass
class DiagnosticRecord:
    """Registro de um diagnostico do Observer pronto para persistir.

    Campos sao todos opcionais para permitir registrar mesmo falhas parciais
    (ex: LLM respondeu mas nao gerou fix, ou LLM nao respondeu).
    """

    id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    job_id: int = 0
    job_name: str = ""
    run_id: int = 0
    failed_task: str = ""
    error_message: str = ""
    error_hash: str = ""
    diagnosis: str = ""
    root_cause: str = ""
    fix_description: str = ""
    file_to_fix: str = ""
    confidence: float = 0.0
    requires_human_review: bool = True
    pr_url: str = ""
    pr_number: int = 0
    branch_name: str = ""
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    status: str = "unknown"

    def to_row_dict(self) -> dict[str, Any]:
        """Converte para dict pronto para spark.createDataFrame."""
        return asdict(self)


class ObserverDiagnosticsStore:
    """Persiste diagnosticos do Observer em uma tabela Delta."""

    SCHEMA_DDL = """
        id                     STRING,
        timestamp              TIMESTAMP,
        job_id                 BIGINT,
        job_name               STRING,
        run_id                 BIGINT,
        failed_task            STRING,
        error_message          STRING,
        error_hash             STRING,
        diagnosis              STRING,
        root_cause             STRING,
        fix_description        STRING,
        file_to_fix            STRING,
        confidence             DOUBLE,
        requires_human_review  BOOLEAN,
        pr_url                 STRING,
        pr_number              INT,
        branch_name            STRING,
        provider               STRING,
        model                  STRING,
        input_tokens           INT,
        output_tokens          INT,
        estimated_cost_usd     DOUBLE,
        duration_seconds       DOUBLE,
        status                 STRING
    """

    def __init__(self, spark: Any, catalog: str = "medallion"):
        self.spark = spark
        self.catalog = catalog
        self.schema = "observer"
        self.table = "diagnostics"

    @property
    def full_table_name(self) -> str:
        return f"{self.catalog}.{self.schema}.{self.table}"

    def ensure_schema(self) -> None:
        """Cria o schema observer e a tabela diagnostics se nao existirem."""
        self.spark.sql(
            f"CREATE SCHEMA IF NOT EXISTS {self.catalog}.{self.schema} "
            f"COMMENT 'Observabilidade do Observer Agent'"
        )
        self.spark.sql(
            f"CREATE TABLE IF NOT EXISTS {self.full_table_name} ("
            f"{self.SCHEMA_DDL}"
            f") USING DELTA "
            f"COMMENT 'Diagnosticos do Observer Agent (LLM + PR + metricas)'"
        )

    def build_record(
        self,
        *,
        job_id: int,
        job_name: str,
        run_id: int,
        failed_task: str,
        error_message: str,
        status: str,
        duration_seconds: float,
        diagnosis: Any | None = None,
        pr_result: Any | None = None,
    ) -> DiagnosticRecord:
        """Constroi um DiagnosticRecord a partir de DiagnosisResult + PRResult.

        Aceita diagnosis/pr_result como None para registrar falhas (LLM falhou,
        nenhum fix gerado, etc).
        """
        record = DiagnosticRecord(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            job_id=int(job_id or 0),
            job_name=job_name or "",
            run_id=int(run_id or 0),
            failed_task=failed_task or "",
            error_message=error_message or "",
            error_hash=error_hash(error_message),
            duration_seconds=round(duration_seconds, 3),
            status=status,
        )

        if diagnosis is not None:
            record.diagnosis = diagnosis.diagnosis or ""
            record.root_cause = diagnosis.root_cause or ""
            record.fix_description = diagnosis.fix_description or ""
            record.file_to_fix = diagnosis.file_to_fix or ""
            record.confidence = float(diagnosis.confidence or 0.0)
            record.requires_human_review = bool(diagnosis.requires_human_review)
            record.provider = diagnosis.provider or ""
            record.model = diagnosis.model or ""
            record.input_tokens = int(diagnosis.input_tokens or 0)
            record.output_tokens = int(diagnosis.output_tokens or 0)
            record.estimated_cost_usd = calculate_cost_usd(
                diagnosis.provider,
                diagnosis.model,
                record.input_tokens,
                record.output_tokens,
            )

        if pr_result is not None:
            record.pr_url = pr_result.pr_url or ""
            record.pr_number = int(pr_result.pr_number or 0)
            record.branch_name = pr_result.branch_name or ""

        return record

    def save(self, record: DiagnosticRecord) -> None:
        """Persiste um DiagnosticRecord na tabela Delta (append)."""
        from pyspark.sql import Row

        row = Row(**record.to_row_dict())
        df = self.spark.createDataFrame([row])
        df.write.format("delta").mode("append").saveAsTable(self.full_table_name)
        logger.info(
            f"Diagnostico {record.id[:8]} salvo em {self.full_table_name} "
            f"(status={record.status}, cost=${record.estimated_cost_usd:.4f})"
        )
