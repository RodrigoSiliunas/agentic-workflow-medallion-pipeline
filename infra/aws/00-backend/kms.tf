# =============================================================================
# KMS — Chave dedicada para encryption do tfstate
# =============================================================================
#
# tfstate costuma conter credenciais efetivas (secret ARNs + valores
# pos-apply dos dados lidos por providers). CMK dedicada + rotation
# anual + alias amigavel.
# =============================================================================

resource "aws_kms_key" "tfstate" {
  description             = "KMS key para o S3 backend do Terraform"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "tfstate" {
  name          = "alias/namastex-tfstate"
  target_key_id = aws_kms_key.tfstate.key_id
}
