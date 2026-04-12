"""Unit tests para CredentialService com mocks de DB e encryption."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.credential_service import CredentialService


def _make_service() -> tuple[CredentialService, MagicMock]:
    """Cria um CredentialService com db mockado."""
    mock_db = AsyncMock()
    service = CredentialService(mock_db)
    return service, mock_db


class TestSetCredential:
    async def test_set_credential_rejects_invalid_type(self):
        """Tipo de credencial invalido deve levantar ValueError."""
        service, _ = _make_service()
        with pytest.raises(ValueError, match="Tipo invalido"):
            await service.set_credential(uuid.uuid4(), "invalid_type", "value")


class TestSetAndGetDecryptedRoundtrip:
    @patch("app.services.credential_service.EncryptionService")
    async def test_set_and_get_decrypted_roundtrip(self, mock_enc_svc):
        """set_credential + get_decrypted deve retornar o valor original."""
        # Configura encryption como identity (valor == encrypted)
        mock_enc = MagicMock()
        mock_enc.encrypt.side_effect = lambda v: f"enc:{v}"
        mock_enc.decrypt.side_effect = lambda v: v.removeprefix("enc:")
        mock_enc_svc.return_value = mock_enc

        mock_db = AsyncMock()
        service = CredentialService(mock_db)
        service.encryption = mock_enc

        company_id = uuid.uuid4()
        original_value = "sk-ant-test-key-12345"

        # Mock: set_credential — nao existe cred anterior
        mock_result_set = MagicMock()
        mock_result_set.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result_set

        await service.set_credential(company_id, "anthropic_api_key", original_value)

        # Verifica que encrypt foi chamado com o valor original
        mock_enc.encrypt.assert_called_once_with(original_value)

        # Mock: get_decrypted — simula encontrar a credencial
        mock_cred = MagicMock()
        mock_cred.encrypted_value = f"enc:{original_value}"
        mock_result_get = MagicMock()
        mock_result_get.scalar_one_or_none.return_value = mock_cred
        mock_db.execute.return_value = mock_result_get

        result = await service.get_decrypted(company_id, "anthropic_api_key")

        assert result == original_value


class TestGetAllDecrypted:
    @patch("app.services.credential_service.EncryptionService")
    async def test_get_all_decrypted_returns_all_company_creds(self, mock_enc_svc):
        """get_all_decrypted deve retornar todas as credenciais decriptadas."""
        mock_enc = MagicMock()
        mock_enc.decrypt.side_effect = lambda v: v.removeprefix("enc:")
        mock_enc_svc.return_value = mock_enc

        mock_db = AsyncMock()
        service = CredentialService(mock_db)
        service.encryption = mock_enc

        # Simula 3 credenciais no DB
        cred1 = MagicMock()
        cred1.credential_type = "aws_access_key_id"
        cred1.encrypted_value = "enc:AKIAEXAMPLE"
        cred2 = MagicMock()
        cred2.credential_type = "aws_secret_access_key"
        cred2.encrypted_value = "enc:secretkey"
        cred3 = MagicMock()
        cred3.credential_type = "databricks_host"
        cred3.encrypted_value = "enc:https://dbc-xxx.cloud.databricks.com"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [cred1, cred2, cred3]
        mock_db.execute.return_value = mock_result

        company_id = uuid.uuid4()
        result = await service.get_all_decrypted(company_id)

        assert len(result) == 3
        assert result["aws_access_key_id"] == "AKIAEXAMPLE"
        assert result["aws_secret_access_key"] == "secretkey"
        assert result["databricks_host"] == "https://dbc-xxx.cloud.databricks.com"


class TestGetDecryptedMissing:
    async def test_get_decrypted_returns_none_for_missing(self):
        """Credencial inexistente deve retornar None."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = CredentialService(mock_db)
        result = await service.get_decrypted(uuid.uuid4(), "anthropic_api_key")

        assert result is None
