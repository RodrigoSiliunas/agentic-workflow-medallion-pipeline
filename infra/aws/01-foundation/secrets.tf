# =============================================================================
# AWS Secrets Manager — Credenciais do projeto
# =============================================================================

# --- Secret: Anthropic API Key ---
resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name        = "${var.project_name}/anthropic-api-key"
  description = "Anthropic API Key para o agente AI do pipeline"

  tags = {
    Purpose  = "ai-agent"
    Rotation = "manual"
  }
}

# --- Secret: GitHub Token ---
resource "aws_secretsmanager_secret" "github_token" {
  name        = "${var.project_name}/github-token"
  description = "GitHub Personal Access Token para auto-PR do agente"

  tags = {
    Purpose  = "agent-github"
    Rotation = "manual"
  }
}

# --- Secret: Databricks Token ---
resource "aws_secretsmanager_secret" "databricks_token" {
  name        = "${var.project_name}/databricks-token"
  description = "Databricks Personal Access Token"

  tags = {
    Purpose  = "databricks-api"
    Rotation = "manual"
  }
}

# --- Secret: Backend Database URL ---
resource "aws_secretsmanager_secret" "database_url" {
  name        = "${var.project_name}/database-url"
  description = "PostgreSQL connection string para o backend FastAPI"

  tags = {
    Purpose  = "backend-database"
    Rotation = "manual"
  }
}

# --- Secret: JWT + Fernet Keys ---
resource "aws_secretsmanager_secret" "backend_keys" {
  name        = "${var.project_name}/backend-keys"
  description = "JWT secret e Fernet key para auth e encryption do backend"

  tags = {
    Purpose  = "backend-auth"
    Rotation = "manual"
  }
}

# NOTA: Os valores dos secrets sao preenchidos manualmente via AWS Console
# ou via: aws secretsmanager put-secret-value --secret-id <name> --secret-string <value>
