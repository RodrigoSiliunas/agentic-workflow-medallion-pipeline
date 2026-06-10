"""Manifesto editavel por template de pipeline."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

SILVER_LAYER = "silver"
EDITOR_LAYERS = (SILVER_LAYER,)

# Catalog Unity default do template WhatsApp (deploy `prod` / legacy). O catalog
# real e resolvido por-pipeline a partir de `pipeline.config["catalog"]`, que o
# saga de deploy persiste com o catalog efetivamente provisionado.
DEFAULT_CATALOG = "medallion"

_CATALOG_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _normalize_catalog(catalog: str | None) -> str:
    """Sanitiza o nome do catalog antes de montar FQNs.

    Cai no default se vazio/invalido — defensivo contra config corrompido,
    evitando montar FQN tipo `..silver.messages_clean` (que viraria SQL ilegal).
    """
    cat = (catalog or "").strip()
    if not cat or not _CATALOG_IDENTIFIER_RE.match(cat):
        return DEFAULT_CATALOG
    return cat


class PipelineManifestNode(BaseModel):
    id: str
    layer: str
    task_key: str
    file_path: str
    input_tables: list[str] = Field(default_factory=list)
    output_tables: list[str] = Field(default_factory=list)
    supported_operations: list[str] = Field(default_factory=list)
    insertion_marker: str
    write_dataframe: str = ""


class PipelineManifest(BaseModel):
    template_slug: str
    display_name: str
    nodes: list[PipelineManifestNode]
    source: str = "embedded"
    editor_layers: list[str] = Field(default_factory=lambda: list(EDITOR_LAYERS))
    # Caminhos relativos ao repo dos notebooks downstream a escanear no approve
    downstream_scan_paths: list[str] = Field(default_factory=list)

    def resolve_node(self, node_id: str) -> PipelineManifestNode:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(f"Pipeline manifest node not found: {node_id}")


def silver_nodes(manifest: PipelineManifest) -> list[PipelineManifestNode]:
    return [node for node in manifest.nodes if node.layer == SILVER_LAYER]


def last_writer_node(
    manifest: PipelineManifest, table: str
) -> PipelineManifestNode | None:
    """Ultimo node (na ordem do pipeline) que escreve `table`.

    Quando mais de um node escreve a mesma tabela (ex.: silver_dedup escreve
    messages_clean e silver_entities a REESCREVE depois), o schema final e o
    do ultimo escritor — operacao de coluna aplicada num escritor anterior
    pode virar no-op silencioso (a coluna pode nem existir la, e o overwrite
    posterior apaga o efeito). Achado no E2E real: rename aplicado no dedup
    nao refletiu na tabela.
    """
    target = table.strip().strip("`").lower()
    found: PipelineManifestNode | None = None
    for node in manifest.nodes:
        if any(t.strip().strip("`").lower() == target for t in node.output_tables):
            found = node
    return found


def manifest_for_editor(manifest: PipelineManifest) -> PipelineManifest:
    """Retorna manifesto filtrado para o editor (Silver only)."""
    return PipelineManifest(
        template_slug=manifest.template_slug,
        display_name=manifest.display_name,
        nodes=silver_nodes(manifest),
        source=manifest.source,
        editor_layers=list(EDITOR_LAYERS),
    )


def ensure_silver_node(manifest: PipelineManifest, node_id: str) -> PipelineManifestNode:
    node = manifest.resolve_node(node_id)
    if node.layer != SILVER_LAYER:
        raise ValueError(
            f"No `{node_id}` pertence a camada `{node.layer}` — "
            "Pipeline Editor aceita apenas Silver."
        )
    return node


_WHATSAPP_GOLD_BASE = "pipelines/pipeline-seguradora-whatsapp/notebooks"

_WHATSAPP_DOWNSTREAM_PATHS: list[str] = [
    f"{_WHATSAPP_GOLD_BASE}/gold/agent_performance.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/campaign_roi.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/churn_reengagement.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/competitor_intel.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/email_providers.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/first_contact_resolution.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/funnel.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/lead_scoring.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/negotiation_complexity.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/outcome_prediction.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/segmentation.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/sentiment.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/sentiment_ml.py",
    f"{_WHATSAPP_GOLD_BASE}/gold/temporal_analysis.py",
    f"{_WHATSAPP_GOLD_BASE}/validation/checks.py",
]


def _common_operations() -> list[str]:
    return [
        "drop_column",
        "rename_column",
        "cast_column",
        "trim",
        "regex_replace",
        "coalesce",
        "derive_column",
        "filter_rows",
        "date_format",
        "json_extract",
        "mask_pii",
    ]


def _whatsapp_manifest(catalog: str = DEFAULT_CATALOG) -> PipelineManifest:
    """Manifesto embutido do template WhatsApp.

    `catalog` parametriza o catalog Unity das tabelas (schema/tabela sao fixos
    do template). Permite que o editor siga o catalog que o deploy realmente
    usou (ex.: `medallion`, `medallion_dev`, `medallion_acme`) ao inves de
    hardcodar `medallion` — caso contrario o preview consulta a tabela errada.
    """
    cat = _normalize_catalog(catalog)
    common_ops = _common_operations()
    return PipelineManifest(
        template_slug="pipeline-seguradora-whatsapp",
        display_name="Pipeline Seguradora WhatsApp",
        source="embedded",
        editor_layers=list(EDITOR_LAYERS),
        downstream_scan_paths=list(_WHATSAPP_DOWNSTREAM_PATHS),
        nodes=[
            PipelineManifestNode(
                id="bronze_ingestion",
                layer="bronze",
                task_key="bronze_ingestion",
                file_path="pipelines/pipeline-seguradora-whatsapp/notebooks/bronze/ingest.py",
                input_tables=[],
                output_tables=[f"{cat}.bronze.conversations"],
                supported_operations=common_ops,
                insertion_marker="# DBTITLE 1,Salvar Bronze Delta",
            ),
            PipelineManifestNode(
                id="silver_dedup",
                layer="silver",
                task_key="silver_dedup",
                file_path="pipelines/pipeline-seguradora-whatsapp/notebooks/silver/dedup_clean.py",
                input_tables=[f"{cat}.bronze.conversations"],
                output_tables=[f"{cat}.silver.messages_clean"],
                supported_operations=common_ops,
                insertion_marker="# DBTITLE 1,Salvar como Delta Table e Upload para S3",
                write_dataframe="df_parsed",
            ),
            PipelineManifestNode(
                id="silver_entities",
                layer="silver",
                task_key="silver_entities",
                file_path="pipelines/pipeline-seguradora-whatsapp/notebooks/silver/entities_mask.py",
                input_tables=[f"{cat}.silver.messages_clean"],
                output_tables=[
                    f"{cat}.silver.messages_clean",
                    f"{cat}.silver.leads_profile",
                ],
                supported_operations=common_ops,
                insertion_marker="# DBTITLE 1,Salvar Messages Clean",
                write_dataframe="df_redacted",
            ),
            PipelineManifestNode(
                id="silver_enrichment",
                layer="silver",
                task_key="silver_enrichment",
                file_path="pipelines/pipeline-seguradora-whatsapp/notebooks/silver/enrichment.py",
                input_tables=[f"{cat}.silver.messages_clean"],
                output_tables=[f"{cat}.silver.conversations_enriched"],
                supported_operations=common_ops,
                insertion_marker="# DBTITLE 1,Salvar no Unity Catalog e S3",
                write_dataframe="conversations",
            ),
            PipelineManifestNode(
                id="gold_analytics",
                layer="gold",
                task_key="gold_analytics",
                file_path="pipelines/pipeline-seguradora-whatsapp/notebooks/gold/analytics.py",
                input_tables=[
                    f"{cat}.silver.leads_profile",
                    f"{cat}.silver.conversations_enriched",
                ],
                output_tables=[f"{cat}.gold.*"],
                supported_operations=common_ops,
                insertion_marker="# DBTITLE 1,Executar Fases Gold",
            ),
        ],
    )


def _manifest_from_config(
    template_slug: str,
    config_manifest: dict[str, Any],
    *,
    template_name: str | None = None,
) -> PipelineManifest:
    raw_nodes = config_manifest.get("nodes") or []
    nodes = [PipelineManifestNode.model_validate(node) for node in raw_nodes]
    return PipelineManifest(
        template_slug=template_slug,
        display_name=str(
            config_manifest.get("display_name") or template_name or template_slug
        ),
        nodes=nodes,
        source="pipeline_config",
        editor_layers=list(EDITOR_LAYERS),
    )


def load_manifest_for_template(
    template_slug: str,
    *,
    template_name: str | None = None,
    config_manifest: dict[str, Any] | None = None,
    catalog: str = DEFAULT_CATALOG,
) -> PipelineManifest:
    """Carrega manifesto do template.

    Prioridade: `pipeline.config.manifest` > manifesto embutido WhatsApp > fallback vazio.
    O editor continua filtrando apenas nos Silver via `manifest_for_editor`.

    `catalog` parametriza o catalog Unity do manifesto embutido — vem de
    `pipeline.config["catalog"]` para o editor seguir o catalog que o deploy
    provisionou. Manifesto vindo de `config.manifest` ja traz FQNs explicitos
    e nao e reescrito.
    """
    if config_manifest and config_manifest.get("nodes"):
        return _manifest_from_config(
            template_slug,
            config_manifest,
            template_name=template_name,
        )

    if template_slug == "pipeline-seguradora-whatsapp":
        return _whatsapp_manifest(catalog=catalog)

    return PipelineManifest(
        template_slug=template_slug,
        display_name=template_name or template_slug,
        nodes=[],
        source="fallback",
        editor_layers=list(EDITOR_LAYERS),
    )
