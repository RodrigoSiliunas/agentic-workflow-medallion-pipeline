import os

import pytest

from pipeline_lib.masking.hash_based import hash_value


class TestHashBased:
    def test_deterministico(self):
        """Mesmo input com mesma chave = mesmo output."""
        os.environ["MASKING_SECRET"] = "test-secret-key"
        h1 = hash_value("38318285605")
        h2 = hash_value("38318285605")
        assert h1 == h2

    def test_diferente_para_inputs_diferentes(self):
        os.environ["MASKING_SECRET"] = "test-secret-key"
        h1 = hash_value("38318285605")
        h2 = hash_value("94296882769")
        assert h1 != h2

    def test_retorna_hex_16_chars(self):
        os.environ["MASKING_SECRET"] = "test-secret-key"
        result = hash_value("38318285605")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_chave_ausente_causa_erro(self):
        """Sem MASKING_SECRET, deve falhar com KeyError."""
        os.environ.pop("MASKING_SECRET", None)
        with pytest.raises(KeyError):
            hash_value("38318285605")

    def test_chaves_diferentes_geram_hashes_diferentes(self):
        os.environ["MASKING_SECRET"] = "key-a"
        h1 = hash_value("38318285605")
        os.environ["MASKING_SECRET"] = "key-b"
        h2 = hash_value("38318285605")
        assert h1 != h2
