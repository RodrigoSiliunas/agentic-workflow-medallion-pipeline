"""Agente estruturado do Pipeline Editor.

MVP determinístico: prepara proposta a partir do DSL recebido pelo chat/builder.
O contrato já permite trocar a implementação por PydanticAI sem mudar rotas.
"""

from __future__ import annotations

from app.services.pipeline_editor.manifest import PipelineManifest, silver_nodes
from app.services.pipeline_editor.schemas import EditProposal, TransformDraft


def build_edit_proposal(
    *,
    user_message: str,
    draft: TransformDraft | None,
    manifest: PipelineManifest,
) -> EditProposal:
    if draft is None:
        target_node = next(iter(silver_nodes(manifest)), None)
        draft = TransformDraft(
            layer="silver",
            target_node=target_node.id if target_node else "silver_dedup",
            target_table=(
                target_node.output_tables[0]
                if target_node and target_node.output_tables
                else "medallion.silver.messages_clean"
            ),
            operations=[],
            warnings=[
                "Nenhuma operacao low-code foi selecionada ainda. "
                "Use o builder ou detalhe colunas/operacoes na conversa."
            ],
        )
    node = manifest.resolve_node(draft.target_node) if manifest.nodes else None
    files = [node.file_path] if node else []
    operation_count = len(draft.operations)
    explanation = (
        f"Proposta estruturada criada para `{draft.target_node}` com "
        f"{operation_count} operacao(oes). Pedido: {user_message}"
    )
    risk = 2 if operation_count <= 2 else 5
    return EditProposal(
        explanation=explanation,
        draft=draft,
        files_affected=files,
        risk_score=risk,
        test_plan=[
            "Validar DSL e codegen.",
            "Executar preview em sandbox tenant-scoped.",
            "Criar PR somente apos aprovacao humana.",
        ],
    )
