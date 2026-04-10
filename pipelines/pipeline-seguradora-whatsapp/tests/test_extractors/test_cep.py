from pipeline_lib.extractors.cep import extract


class TestCepExtract:
    def test_cep_com_hifen(self):
        assert extract("cep 08617-986") == ["08617-986"]

    def test_cep_sem_hifen(self):
        assert extract("cep 60141953") == ["60141953"]

    def test_multiplos_ceps(self):
        text = "cep 08617-986 e 60141-953"
        assert len(extract(text)) == 2

    def test_sem_cep(self):
        assert extract("oi, tudo bem?") == []

    def test_texto_vazio(self):
        assert extract("") == []
        assert extract(None) == []
