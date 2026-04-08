from pipeline_lib.extractors.price import extract


class TestPriceExtract:
    def test_preco_simples(self):
        result = extract("HDI me ofereceu por R$ 1903")
        assert 1903.0 in result

    def test_preco_com_centavos(self):
        result = extract("fica R$ 2.500,00 por ano")
        assert 2500.0 in result

    def test_preco_com_virgula(self):
        result = extract("pago R$ 4891 na Bradesco")
        assert 4891.0 in result

    def test_multiplos_precos(self):
        result = extract("um eh R$ 1500 e outro R$ 2000")
        assert len(result) == 2

    def test_sem_preco(self):
        assert extract("oi, quero seguro") == []

    def test_texto_vazio(self):
        assert extract("") == []
        assert extract(None) == []
