from pipeline_lib.schema.contracts import REQUIRED_COLUMNS
from pipeline_lib.schema.validator import validate_schema


class TestValidateSchema:
    """Testes para validacao de schema com evolution."""

    def test_schema_valido_com_todas_colunas_obrigatorias(self):
        """Schema com exatamente as 14 colunas obrigatorias deve passar."""
        result = validate_schema(set(REQUIRED_COLUMNS))
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_schema_valido_com_colunas_extras(self):
        """Schema com colunas obrigatorias + extras deve passar com warnings."""
        columns = set(REQUIRED_COLUMNS) | {"new_feature", "utm_source"}
        result = validate_schema(columns)
        assert result.is_valid is True
        assert result.errors == []
        assert len(result.warnings) > 0
        assert "new_feature" in str(result.warnings)
        assert "utm_source" in str(result.warnings)

    def test_schema_invalido_sem_coluna_obrigatoria(self):
        """Schema faltando coluna obrigatoria deve falhar."""
        columns = set(REQUIRED_COLUMNS) - {"message_body"}
        result = validate_schema(columns)
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "message_body" in str(result.errors)

    def test_schema_invalido_sem_multiplas_colunas(self):
        """Schema faltando varias colunas obrigatorias deve listar todas."""
        columns = set(REQUIRED_COLUMNS) - {"message_body", "conversation_id", "timestamp"}
        result = validate_schema(columns)
        assert result.is_valid is False
        assert len(result.errors) > 0
        for col in ["message_body", "conversation_id", "timestamp"]:
            assert col in str(result.errors)

    def test_schema_vazio_falha(self):
        """Schema sem nenhuma coluna deve falhar."""
        result = validate_schema(set())
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_schema_com_apenas_colunas_extras_falha(self):
        """Schema com colunas que nao sao obrigatorias deve falhar."""
        result = validate_schema({"random_col", "another_col"})
        assert result.is_valid is False

    def test_nova_coluna_listada_nos_warnings(self):
        """Colunas novas devem aparecer nos warnings, nao nos erros."""
        columns = set(REQUIRED_COLUMNS) | {"lead_score_external"}
        result = validate_schema(columns)
        assert result.is_valid is True
        assert "lead_score_external" in str(result.warnings)
        assert "lead_score_external" not in str(result.errors)

    def test_required_columns_tem_14_colunas(self):
        """Contrato deve ter exatamente 14 colunas obrigatorias."""
        assert len(REQUIRED_COLUMNS) == 14
