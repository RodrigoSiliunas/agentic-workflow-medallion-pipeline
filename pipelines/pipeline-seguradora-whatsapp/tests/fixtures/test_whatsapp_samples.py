"""Smoke tests das fixtures WhatsApp — garante que não quebrem (T6 Phase 4)."""

from __future__ import annotations

import pytest

from tests.fixtures.whatsapp_samples import WHATSAPP_MESSAGE_SAMPLES


def test_has_minimum_variety():
    """Precisa cobrir ao menos PII, vazio, multi-linha e emoji."""
    labels = {s.label for s in WHATSAPP_MESSAGE_SAMPLES}
    assert "empty" in labels
    assert "emoji_heavy" in labels
    assert "multiline_quote" in labels
    assert "audio_transcript" in labels


def test_labels_are_unique():
    labels = [s.label for s in WHATSAPP_MESSAGE_SAMPLES]
    assert len(labels) == len(set(labels))


@pytest.mark.parametrize("sample", WHATSAPP_MESSAGE_SAMPLES, ids=lambda s: s.label)
def test_pii_flags_consistent_with_body(sample):
    """Se o sample marca has_cpf/has_phone/has_email/has_plate, o body
    deve ao menos conter um padrão detectável do respectivo tipo."""
    if sample.has_cpf:
        assert any(c.isdigit() for c in sample.body)
    if sample.has_email:
        assert "@" in sample.body
    # has_phone e has_plate — tolera varias variações de formato
    if sample.has_phone:
        assert any(c.isdigit() for c in sample.body)
    if sample.has_plate:
        # Placas Mercosul ou antigas têm letras + dígitos
        assert any(c.isalpha() for c in sample.body)
        assert any(c.isdigit() for c in sample.body)
