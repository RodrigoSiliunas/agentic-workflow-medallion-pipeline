"""Unit tests para o model OmniInstance (shape)."""

from sqlalchemy import inspect

from app.models.channel import OmniInstance


def test_tablename():
    assert OmniInstance.__tablename__ == "omni_instances"


def test_required_columns_exist():
    mapper = inspect(OmniInstance)
    columns = {c.key for c in mapper.columns}
    expected = {
        "id",
        "company_id",
        "omni_instance_id",
        "name",
        "channel",
        "state",
        "last_sync_at",
        "last_error",
        "created_at",
        "updated_at",
    }
    missing = expected - columns
    assert not missing, f"columns faltando: {missing}"


def test_company_id_is_foreign_key():
    mapper = inspect(OmniInstance)
    company_col = mapper.columns["company_id"]
    assert company_col.foreign_keys, "company_id deveria ser FK"
    fk = next(iter(company_col.foreign_keys))
    assert fk.column.table.name == "companies"
    assert fk.ondelete == "CASCADE"


def test_omni_instance_id_nullable():
    """Deve ser nullable para permitir failed antes da criacao no Omni."""
    mapper = inspect(OmniInstance)
    assert mapper.columns["omni_instance_id"].nullable is True


def test_state_indexed():
    mapper = inspect(OmniInstance)
    assert mapper.columns["state"].index is True
