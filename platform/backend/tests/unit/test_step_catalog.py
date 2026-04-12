"""Unit tests para CatalogStep — validacao do nome do catalog."""



from app.services.real_saga.steps.catalog import _IDENTIFIER_RE


class TestCatalogNameValidation:
    def test_catalog_name_validation_accepts_valid(self):
        """'medallion' deve ser aceito pelo regex."""
        assert _IDENTIFIER_RE.match("medallion") is not None

    def test_catalog_name_validation_accepts_with_numbers(self):
        """Nome com numeros e underscores deve ser aceito."""
        assert _IDENTIFIER_RE.match("medallion_v2") is not None

    def test_catalog_name_validation_rejects_injection(self):
        """'medallion; DROP' nao deve ser aceito — previne SQL injection."""
        assert _IDENTIFIER_RE.match("medallion; DROP") is None

    def test_catalog_name_validation_rejects_uppercase(self):
        """'Medallion' (com maiuscula) nao deve ser aceito."""
        assert _IDENTIFIER_RE.match("Medallion") is None

    def test_catalog_name_validation_rejects_starting_with_number(self):
        """Nome comecando com numero nao deve ser aceito."""
        assert _IDENTIFIER_RE.match("2catalog") is None

    def test_catalog_name_validation_rejects_empty(self):
        """String vazia nao deve ser aceita."""
        assert _IDENTIFIER_RE.match("") is None

    def test_catalog_name_validation_rejects_too_long(self):
        """Nomes com mais de 64 caracteres nao devem ser aceitos."""
        long_name = "a" * 65
        assert _IDENTIFIER_RE.match(long_name) is None

    def test_catalog_name_validation_accepts_max_length(self):
        """Nome com exatamente 64 caracteres deve ser aceito."""
        name_64 = "a" * 64
        assert _IDENTIFIER_RE.match(name_64) is not None
