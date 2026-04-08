from pipeline_lib.extractors.plate import extract, mask


class TestPlateExtract:
    def test_placa_mercosul(self):
        assert extract("placa SYL8V26") == ["SYL8V26"]

    def test_placa_mercosul_2(self):
        assert extract("placa XPZ9O36") == ["XPZ9O36"]

    def test_placa_em_contexto(self):
        result = extract("Onix ano 2015 cor prata, placa SYL8V26")
        assert "SYL8V26" in result

    def test_placa_com_ponto(self):
        result = extract("a placa eh EYQ7T91")
        assert "EYQ7T91" in result

    def test_sem_placa(self):
        assert extract("oi, quero seguro") == []

    def test_texto_vazio(self):
        assert extract("") == []
        assert extract(None) == []


class TestPlateMask:
    def test_mask_placa(self):
        result = mask("SYL8V26")
        assert len(result) == 7
        assert result[0] == "S"
