# =============================================================================
# IAM Users — Acesso programatico para pipeline e servicos
# =============================================================================

# --- Pipeline CI/CD User ---
resource "aws_iam_user" "pipeline" {
  count = var.create_pipeline_user ? 1 : 0

  name = "${var.project_name}-pipeline-user"
  path = "/service-accounts/"

  tags = {
    Purpose = "pipeline-cicd"
  }
}

resource "aws_iam_access_key" "pipeline" {
  count = var.create_pipeline_user ? 1 : 0

  user = aws_iam_user.pipeline[0].name
}

# Guardar credenciais no Secrets Manager
resource "aws_secretsmanager_secret" "pipeline_credentials" {
  count = var.create_pipeline_user ? 1 : 0

  name        = "${var.project_name}/pipeline-user-credentials"
  description = "Access key do pipeline CI/CD user"

  tags = {
    Purpose = "pipeline-cicd"
  }
}

resource "aws_secretsmanager_secret_version" "pipeline_credentials" {
  count = var.create_pipeline_user ? 1 : 0

  secret_id = aws_secretsmanager_secret.pipeline_credentials[0].id
  secret_string = jsonencode({
    access_key_id     = aws_iam_access_key.pipeline[0].id
    secret_access_key = aws_iam_access_key.pipeline[0].secret
  })
}

# --- Policy: Pipeline user pode acessar S3 + Secrets Manager ---
resource "aws_iam_user_policy_attachment" "pipeline_s3" {
  count = var.create_pipeline_user ? 1 : 0

  user       = aws_iam_user.pipeline[0].name
  policy_arn = aws_iam_policy.pipeline_s3_access.arn
}

resource "aws_iam_user_policy_attachment" "pipeline_secrets" {
  count = var.create_pipeline_user ? 1 : 0

  user       = aws_iam_user.pipeline[0].name
  policy_arn = aws_iam_policy.pipeline_secrets_read.arn
}
