from pipeline_lib.extractors.competitor import extract


class TestCompetitorExtract:
    def test_hdi(self):
        result = extract("HDI Seguros me ofereceu por R$ 1903")
        assert "hdi" in result

    def test_bradesco(self):
        result = extract("meu amigo paga R$ 4891 na Bradesco Seguros")
        assert "bradesco" in result

    def test_porto_seguro(self):
        result = extract("tenho seguro da Porto Seguro")
        assert "porto seguro" in result

    def test_multiplos_concorrentes(self):
        result = extract("comparei Porto Seguro e Azul Seguros")
        assert len(result) >= 2

    def test_sem_concorrente(self):
        assert extract("oi, quero seguro") == []

    def test_texto_vazio(self):
        assert extract("") == []
        assert extract(None) == []
