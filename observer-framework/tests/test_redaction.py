"""Testes de redação PII (T1 Phase 3)."""

from __future__ import annotations

import pytest

from observer.redaction import PIIRedactor, redact


class TestSingleValues:
    @pytest.mark.parametrize(
        "raw,label",
        [
            ("123.456.789-09", "CPF"),
            ("11.222.333/0001-81", "CNPJ"),
            ("+55 (11) 98765-4321", "PHONE_BR"),
            ("(11) 98765-4321", "PHONE_BR"),
            ("11987654321", "PHONE_BR"),
            ("foo@example.com", "EMAIL"),
            ("customer.name+alias@sub.example.co.uk", "EMAIL"),
            ("Bearer abc.def.ghi", "BEARER_TOKEN"),
            ("AKIAIOSFODNN7EXAMPLE", "AWS_KEY"),
            ("ghp_1234567890abcdef1234567890abcdef12", "GITHUB_PAT"),
            ("sk-ant-api03-ABC123DEF456GHI789", "ANTHROPIC_KEY"),
        ],
    )
    def test_redacts(self, raw: str, label: str):
        out = redact(raw)
        assert raw not in out, f"{label} não foi redigido"
        assert f"<REDACTED:{label}>" in out


class TestMultiplePii:
    def test_traceback_sample(self):
        traceback = (
            "Traceback (most recent call last):\n"
            "  File '/notebook/bronze/ingest.py', line 42\n"
            "ValueError: failed to parse message from "
            "+55 (11) 98765-4321 "
            "(CPF 123.456.789-09, email user@test.com). "
            "Auth header: Bearer ghp_1234567890abcdef1234567890abcdef12"
        )
        out = redact(traceback)
        # Não deve conter nenhum dado sensível
        assert "123.456.789-09" not in out
        assert "user@test.com" not in out
        assert "98765-4321" not in out
        assert "ghp_" not in out
        # Labels esperados
        assert "<REDACTED:CPF>" in out
        assert "<REDACTED:EMAIL>" in out
        assert "<REDACTED:PHONE_BR>" in out

    def test_cnpj_prioritized_over_cpf(self):
        # CNPJ tem 14 dígitos — se CPF regex consumisse antes, sobraria lixo
        out = redact("CNPJ 11.222.333/0001-81 ativo")
        assert "<REDACTED:CNPJ>" in out
        assert "11.222.333" not in out

    def test_no_pii_unchanged(self):
        plain = "Pipeline bronze ingest runiu 12 files em 3.2s"
        assert redact(plain) == plain


class TestEdgeCases:
    def test_empty_string(self):
        assert redact("") == ""

    def test_none_returns_empty(self):
        assert redact(None) == ""

    def test_redact_dict_preserves_keys(self):
        redactor = PIIRedactor()
        payload = {
            "task": "bronze_ingest",
            "error": "CPF 111.222.333-44 inválido",
            "meta": {"user_email": "a@b.com", "run_id": 42},
            "attempts": ["ping +55 11 98765-4321 falhou", "ok"],
        }
        out = redactor.redact_dict(payload)
        assert out["task"] == "bronze_ingest"
        assert "<REDACTED:CPF>" in out["error"]
        assert "<REDACTED:EMAIL>" in out["meta"]["user_email"]
        assert out["meta"]["run_id"] == 42  # int preservado
        assert "<REDACTED:PHONE_BR>" in out["attempts"][0]
        assert out["attempts"][1] == "ok"
