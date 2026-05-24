"""Contratos estruturados do Pipeline Editor.

Chat e builder low-code escrevem o mesmo DSL para evitar que o LLM edite
arquivos livremente.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

SUPPORTED_OPERATIONS = {
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
}


class TransformOperation(BaseModel):
    """Uma operacao declarativa de transformacao."""

    op: str
    column: str | None = None
    new_name: str | None = None
    data_type: str | None = None
    pattern: str | None = None
    replacement: str | None = None
    expression: str | None = None
    format: str | None = None
    json_path: str | None = None
    source_columns: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_operation(self) -> TransformOperation:
        if self.op not in SUPPORTED_OPERATIONS:
            raise ValueError(f"Unsupported transform operation: {self.op}")
        if (
            self.op in {"drop_column", "rename_column", "cast_column", "trim", "regex_replace"}
            and not self.column
        ):
            raise ValueError(f"Operation {self.op} requires column")
        if self.op == "rename_column" and not self.new_name:
            raise ValueError("rename_column requires new_name")
        if self.op == "cast_column" and not self.data_type:
            raise ValueError("cast_column requires data_type")
        if self.op == "regex_replace" and (self.pattern is None or self.replacement is None):
            raise ValueError("regex_replace requires pattern and replacement")
        if self.op == "derive_column" and (not self.column or not self.expression):
            raise ValueError("derive_column requires column and expression")
        if self.op == "filter_rows" and not self.expression:
            raise ValueError("filter_rows requires expression")
        if self.op == "date_format" and (not self.column or not self.format):
            raise ValueError("date_format requires column and format")
        if self.op == "json_extract" and (
            not self.column or not self.json_path or not self.new_name
        ):
            raise ValueError("json_extract requires column, json_path and new_name")
        return self


class TransformDraft(BaseModel):
    """Draft versionado de edicao do pipeline."""

    layer: Literal["bronze", "silver", "gold"]
    target_node: str
    target_table: str
    operations: list[TransformOperation] = Field(default_factory=list)
    input_dataframe: str = "df_parsed"
    output_dataframe: str = "df_editor"
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_editor_scope(self) -> TransformDraft:
        if self.layer != "silver":
            raise ValueError(
                "Pipeline Editor suporta apenas camada Silver no momento."
            )
        return self


class EditProposal(BaseModel):
    """Saida estruturada do agente de edicao."""

    explanation: str
    draft: TransformDraft
    files_affected: list[str] = Field(default_factory=list)
    risk_score: int = Field(default=3, ge=0, le=10)
    test_plan: list[str] = Field(default_factory=list)
