from pipeline_lib.extractors.cpf import extract, mask, validate


class TestCpfExtract:
    def test_cpf_com_pontuacao(self):
        assert extract("meu cpf eh 383.182.856-05") == ["383.182.856-05"]

    def test_cpf_sem_pontuacao(self):
        assert extract("cpf 38318285605") == ["38318285605"]

    def test_multiplos_cpfs(self):
        text = "cpf 942.968.827-69 e tambem 383.182.856-05"
        result = extract(text)
        assert len(result) == 2

    def test_cpf_em_audio_transcrito(self):
        text = "[audio transcrito] o cpf eh 418.696.561-30"
        assert extract(text) == ["418.696.561-30"]

    def test_sem_cpf(self):
        assert extract("oi, quero saber sobre o seguro") == []

    def test_texto_vazio(self):
        assert extract("") == []
        assert extract(None) == []


class TestCpfValidate:
    def test_cpf_valido(self):
        assert validate("529.982.247-25") is True

    def test_cpf_invalido_digitos(self):
        assert validate("111.111.111-11") is False

    def test_cpf_invalido_formato(self):
        assert validate("abc") is False


class TestCpfMask:
    def test_mask_preserva_formato(self):
        assert mask("383.182.856-05") == "***.***.856-05"

    def test_mask_sem_pontuacao(self):
        result = mask("38318285605")
        assert "856-05" in result or "85605" in result
