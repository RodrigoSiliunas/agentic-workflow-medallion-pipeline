from pipeline_lib.extractors.phone import extract, mask


class TestPhoneExtract:
    def test_telefone_com_parenteses(self):
        result = extract("me liga (11) 98765-4321")
        assert len(result) == 1

    def test_telefone_com_55(self):
        result = extract("+5511988734012")
        assert len(result) == 1

    def test_sem_telefone(self):
        assert extract("oi, tudo bem?") == []

    def test_texto_vazio(self):
        assert extract("") == []
        assert extract(None) == []


class TestPhoneMask:
    def test_mask_preserva_ddd(self):
        result = mask("(11) 98765-4321")
        assert result.startswith("(11)")
        assert result.endswith("4321")
