# =============================================================================
# AWS Secrets Manager — Credenciais do projeto
# =============================================================================
#
# Todos os secrets usam:
# - KMS CMK dedicada (`alias/namastex-secrets`) — permite rotation e
#   auditoria isoladas das outras keys do projeto.
# - `recovery_window_in_days = 7` — janela de recuperacao apos delete
#   (evita delete acidental que bloquearia o pipeline).
#
# NOTA: Valores dos secrets sao preenchidos fora do Terraform via
# AWS Console ou `aws secretsmanager put-secret-value`. Manual por
# enquanto; rotation via Lambda fica pra quando migrarmos o DB pra RDS
# (unica credencial rotacionavel sem quebra externa).
# =============================================================================

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name        = "${var.project_name}/anthropic-api-key"
  description = "Anthropic API Key para o agente AI do pipeline"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 7

  tags = {
    Purpose  = "ai-agent"
    Rotation = "manual"
  }
}

resource "aws_secretsmanager_secret" "github_token" {
  name        = "${var.project_name}/github-token"
  description = "GitHub Personal Access Token para auto-PR do agente"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 7

  tags = {
    Purpose  = "agent-github"
    Rotation = "manual"
  }
}

resource "aws_secretsmanager_secret" "databricks_token" {
  name        = "${var.project_name}/databricks-token"
  description = "Databricks Personal Access Token"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 7

  tags = {
    Purpose  = "databricks-api"
    Rotation = "manual"
  }
}

resource "aws_secretsmanager_secret" "database_url" {
  name        = "${var.project_name}/database-url"
  description = "PostgreSQL connection string para o backend FastAPI"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 7

  tags = {
    Purpose = "backend-database"
    # Quando migrarmos pra RDS, adicionar aws_secretsmanager_secret_rotation
    # apontando pra Lambda provisionada com `aws_secretsmanager_rotate_secret`.
    Rotation = "manual"
  }
}

resource "aws_secretsmanager_secret" "backend_keys" {
  name        = "${var.project_name}/backend-keys"
  description = "JWT secret e Fernet key para auth e encryption do backend"

  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 7

  tags = {
    Purpose  = "backend-auth"
    Rotation = "manual"
  }
}
