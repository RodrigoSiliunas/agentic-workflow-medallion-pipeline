"""Samples realistas de mensagens WhatsApp para pytest (T6 Phase 4).

Cobre casos que aparecem em prod:
- Texto curto, multi-linha, com emoji
- Transcrição de áudio (com quebras e tipos variados)
- PII embutida (CPF, telefone, email, placa)
- Casos vazios / corrompidos

Uso:
    from tests.fixtures import WHATSAPP_MESSAGE_SAMPLES

    @pytest.mark.parametrize("sample", WHATSAPP_MESSAGE_SAMPLES)
    def test_redaction(sample):
        ...
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WhatsAppMessage:
    """Sample imutável de uma mensagem WhatsApp típica."""

    label: str
    body: str
    has_cpf: bool = False
    has_phone: bool = False
    has_email: bool = False
    has_plate: bool = False


WHATSAPP_MESSAGE_SAMPLES: list[WhatsAppMessage] = [
    WhatsAppMessage(
        label="simple_greeting",
        body="Ola, tudo bem?",
    ),
    WhatsAppMessage(
        label="multiline_quote",
        body=(
            "Segue cotacao:\n"
            "- Valor anual: R$ 3.200\n"
            "- Franquia: R$ 1.800\n"
            "- Assistencia 24h incluso\n"
            "Aceita?"
        ),
    ),
    WhatsAppMessage(
        label="emoji_heavy",
        body="Obrigada! 😊🙏 Vou pensar aqui 💭",
    ),
    WhatsAppMessage(
        label="audio_transcript",
        body=(
            "[AUDIO]: Oi, boa tarde. "
            "Estou com o carro na oficina e queria saber se voces cobrem "
            "esse tipo de servico no meu seguro. "
            "Meu nome e Maria e o veiculo e o ABC1D23."
        ),
        has_plate=True,
    ),
    WhatsAppMessage(
        label="cpf_inbound",
        body="Pode cadastrar com meu CPF 123.456.789-09",
        has_cpf=True,
    ),
    WhatsAppMessage(
        label="phone_brazil",
        body="Me liga no +55 (11) 98765-4321",
        has_phone=True,
    ),
    WhatsAppMessage(
        label="email_plus_phone",
        body=(
            "Contato: maria.silva+seguro@gmail.com. "
            "WhatsApp 11987654321."
        ),
        has_email=True,
        has_phone=True,
    ),
    WhatsAppMessage(
        label="full_pii_bundle",
        body=(
            "CPF 123.456.789-09, tel (11) 98765-4321, "
            "email maria@empresa.com.br, placa ABC1D23, "
            "veiculo Onix 2022"
        ),
        has_cpf=True,
        has_phone=True,
        has_email=True,
        has_plate=True,
    ),
    WhatsAppMessage(
        label="empty",
        body="",
    ),
    WhatsAppMessage(
        label="whitespace_only",
        body="   \n\n  \t  ",
    ),
    WhatsAppMessage(
        label="url_and_mention",
        body="Detalhes em https://seguradoraX.com.br/cotacao",
    ),
    WhatsAppMessage(
        label="mercosul_and_old_plate",
        body="Tenho dois carros: ABC-1234 e BRA2E19",
        has_plate=True,
    ),
    WhatsAppMessage(
        label="long_narrative",
        body=(
            "Oi, tudo bem? Deixa eu te explicar a situacao:\n"
            "semana passada meu carro bateu na traseira de outro\n"
            "quando eu vinha da academia. O outro motorista ligou "
            "pra policia e a gente fez o BO. Depois do BO ele me mandou "
            "uma foto do documento, o CPF dele e 111.222.333-44 e o "
            "telefone e 11912345678. Posso enviar pra voces tudo isso?"
        ),
        has_cpf=True,
        has_phone=True,
    ),
]
