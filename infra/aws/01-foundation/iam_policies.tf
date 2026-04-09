# =============================================================================
# IAM Policies — Reusaveis entre users e roles
# =============================================================================

# --- S3 Data Lake Access (Databricks) ---
resource "aws_iam_policy" "databricks_s3_access" {
  name        = "${var.project_name}-databricks-s3-access"
  description = "Permite Databricks acessar o data lake S3 (leitura, escrita, listagem)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ReadWrite"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*",
        ]
      },
      {
        Sid    = "S3ListAll"
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets",
          "s3:GetBucketLocation",
        ]
        Resource = "arn:aws:s3:::*"
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}

# --- S3 Pipeline Access (para CI/CD user e agent role) ---
resource "aws_iam_policy" "pipeline_s3_access" {
  name        = "${var.project_name}-pipeline-s3-access"
  description = "Acesso S3 para pipeline (upload dados, leitura resultados)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3FullAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetObjectVersion",
          "s3:ListBucketVersions",
        ]
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*",
        ]
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}

# --- Secrets Manager Read (para ler credenciais) ---
resource "aws_iam_policy" "pipeline_secrets_read" {
  name        = "${var.project_name}-secrets-read"
  description = "Leitura de secrets do pipeline no Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsRead"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project_name}/*"
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}

# --- STS para Databricks (pass role + self-assume) ---
resource "aws_iam_policy" "databricks_sts" {
  name        = "${var.project_name}-databricks-sts"
  description = "Permite Databricks criar sessoes temporarias e self-assume (requisito Unity Catalog)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSelfAssume"
        Effect = "Allow"
        Action = [
          "sts:AssumeRole",
          "sts:TagSession",
        ]
        Resource = "arn:aws:iam::051457670776:role/service-roles/${var.project_name}-databricks-role"
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}

# Attach STS policy ao Databricks role
resource "aws_iam_role_policy_attachment" "databricks_sts" {
  role       = aws_iam_role.databricks_cross_account.name
  policy_arn = aws_iam_policy.databricks_sts.arn
}
