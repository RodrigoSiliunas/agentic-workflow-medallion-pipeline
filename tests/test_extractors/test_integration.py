"""Teste de integracao: fluxo Silver com mini-dataset sintetico."""

from pipeline_lib.extractors import cep, competitor, cpf, email, phone, plate, price, vehicle
from pipeline_lib.masking.format_preserving import mask_cpf, mask_email, mask_plate
from pipeline_lib.masking.redaction import redact_message_body

# Mensagens reais do dataset (anonimizadas para teste)
SAMPLE_MESSAGES = [
    "meu cpf eh 529.982.247-25, cep 08617-986 e email joao.santos@yahoo.com.br",
    "Onix ano 2015 cor prata, placa SYL8V26",
    "hmm nao sei nao, HDI Seguros me ofereceu por R$ 1903",
    "eh Civic 2016.. placa XPZ9O36. ta em bom estado",
    "oi, quero saber sobre o seguro",
    "",
    None,
]


class TestIntegrationExtractionPipeline:
    """Testa o fluxo completo: extracao -> mascaramento -> redaction."""

    def test_mensagem_com_cpf_email_cep(self):
        msg = SAMPLE_MESSAGES[0]

        cpfs = cpf.extract(msg)
        assert len(cpfs) == 1
        assert cpfs[0] == "529.982.247-25"

        emails = email.extract(msg)
        assert len(emails) == 1
        assert emails[0] == "joao.santos@yahoo.com.br"

        ceps = cep.extract(msg)
        assert len(ceps) == 1

        # Mascaramento preserva formato
        masked = mask_cpf(cpfs[0])
        assert masked == "***.***.247-25"

        masked_email = mask_email(emails[0])
        assert "@yahoo.com.br" in masked_email
        assert "joao.santos" not in masked_email

    def test_mensagem_com_veiculo_placa(self):
        msg = SAMPLE_MESSAGES[1]

        v = vehicle.extract(msg)
        assert v["model"] == "onix"
        assert v["brand"] == "chevrolet"
        assert v["year"] == "2015"

        plates = plate.extract(msg)
        assert "SYL8V26" in plates

        masked = mask_plate("SYL8V26")
        assert masked == "S**8*26"

    def test_mensagem_com_concorrente_preco(self):
        msg = SAMPLE_MESSAGES[2]

        comps = competitor.extract(msg)
        assert "hdi" in comps

        prices = price.extract(msg)
        assert 1903.0 in prices

    def test_redaction_remove_todos_pii(self):
        msg = SAMPLE_MESSAGES[0]
        redacted = redact_message_body(msg)

        # CPF original nao deve estar presente
        assert "529.982.247-25" not in redacted
        # Email original nao deve estar presente
        assert "joao.santos@yahoo.com.br" not in redacted
        # Mas versoes mascaradas sim
        assert "***.***.247-25" in redacted
        assert "@yahoo.com.br" in redacted

    def test_redaction_preserva_texto_sem_pii(self):
        msg = SAMPLE_MESSAGES[4]
        assert redact_message_body(msg) == msg

    def test_redaction_texto_vazio_e_none(self):
        assert redact_message_body("") == ""
        assert redact_message_body(None) is None

    def test_pipeline_completo_todas_mensagens(self):
        """Nenhuma mensagem deve causar excecao no pipeline."""
        for msg in SAMPLE_MESSAGES:
            # Extracao
            cpf.extract(msg)
            email.extract(msg)
            phone.extract(msg)
            plate.extract(msg)
            cep.extract(msg)
            competitor.extract(msg)
            price.extract(msg)
            vehicle.extract(msg)

            # Redaction
            redact_message_body(msg)
