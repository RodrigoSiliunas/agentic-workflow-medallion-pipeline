# =============================================================================
# KMS — Customer Managed Keys para datalake e secrets
# =============================================================================
#
# Chaves dedicadas por dominio facilitam:
#   - Rotation independente por tipo de dado
#   - Auditoria (CloudTrail por key)
#   - Separacao de permissoes (quem cripta secrets != quem cripta dados)
#
# `enable_key_rotation = true` faz AWS girar a key material anualmente
# sem precisar atualizar ciphertext antigo.
# =============================================================================

resource "aws_kms_key" "datalake" {
  description             = "KMS CMK para encryption dos buckets do data lake"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Purpose = "datalake-encryption"
  }
}

resource "aws_kms_alias" "datalake" {
  name          = "alias/flowertex-datalake"
  target_key_id = aws_kms_key.datalake.key_id
}

resource "aws_kms_key" "secrets" {
  description             = "KMS CMK para encryption dos Secrets Manager"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Purpose = "secrets-encryption"
  }
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/flowertex-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}
