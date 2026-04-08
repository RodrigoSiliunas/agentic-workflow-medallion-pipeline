from pipeline_lib.extractors.email import extract, mask


class TestEmailExtract:
    def test_email_simples(self):
        assert extract("email joao.santos@yahoo.com.br") == ["joao.santos@yahoo.com.br"]

    def test_email_outlook(self):
        assert extract("lucas.souza@outlook.com") == ["lucas.souza@outlook.com"]

    def test_multiplos_emails(self):
        text = "emails: a@gmail.com e b@hotmail.com"
        assert len(extract(text)) == 2

    def test_sem_email(self):
        assert extract("oi, tudo bem?") == []

    def test_texto_vazio(self):
        assert extract("") == []
        assert extract(None) == []


class TestEmailMask:
    def test_mask_preserva_dominio(self):
        assert mask("joao.silva@gmail.com") == "j********a@gmail.com"

    def test_mask_email_curto(self):
        result = mask("ab@gmail.com")
        assert "@gmail.com" in result
