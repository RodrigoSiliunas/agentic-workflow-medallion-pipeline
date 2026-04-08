from pipeline_lib.masking.redaction import redact_message_body


class TestRedaction:
    def test_redact_cpf(self):
        text = "meu cpf eh 383.182.856-05"
        result = redact_message_body(text)
        assert "383.182.856-05" not in result
        assert "***.***.856-05" in result

    def test_redact_email(self):
        text = "email joao.santos@yahoo.com.br"
        result = redact_message_body(text)
        assert "joao.santos@yahoo.com.br" not in result
        assert "@yahoo.com.br" in result

    def test_redact_placa(self):
        text = "placa SYL8V26"
        result = redact_message_body(text)
        assert "SYL8V26" not in result

    def test_texto_sem_pii(self):
        text = "oi, quero saber sobre o seguro"
        assert redact_message_body(text) == text

    def test_texto_vazio(self):
        assert redact_message_body("") == ""
        assert redact_message_body(None) is None

    def test_multiplos_pii(self):
        text = "cpf 383.182.856-05, email ana@gmail.com, placa XPZ9O36"
        result = redact_message_body(text)
        assert "383.182.856-05" not in result
        assert "ana@gmail.com" not in result
        assert "XPZ9O36" not in result
