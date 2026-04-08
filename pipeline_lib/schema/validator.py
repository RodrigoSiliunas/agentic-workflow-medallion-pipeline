"""Validacao de schema com suporte a evolution."""

from dataclasses import dataclass, field

from pipeline_lib.schema.contracts import REQUIRED_COLUMNS


@dataclass
class SchemaValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_schema(df_columns: set[str]) -> SchemaValidationResult:
    """Valida schema contra colunas obrigatorias, aceitando colunas novas.

    Retorna is_valid=True se todas as colunas obrigatorias estao presentes.
    Colunas extras geram warnings (schema evolution), nao erros.
    """
    missing = REQUIRED_COLUMNS - df_columns
    new_cols = df_columns - REQUIRED_COLUMNS

    errors = []
    warnings = []

    if missing:
        errors.append(f"Colunas obrigatorias ausentes: {sorted(missing)}")

    if new_cols:
        warnings.append(
            f"{len(new_cols)} colunas novas detectadas: {sorted(new_cols)}. "
            "Serao preservadas nas camadas subsequentes."
        )

    return SchemaValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
