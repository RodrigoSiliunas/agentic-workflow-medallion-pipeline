# =============================================================================
# IAM Roles — Databricks Cross-Account + Pipeline Agent
# =============================================================================

# --- Databricks Cross-Account Role ---
# Usada pelo Databricks para acessar recursos AWS (S3, etc.)
# O trust policy permite que o Databricks account assuma esta role
resource "aws_iam_role" "databricks_cross_account" {
  name = "${var.project_name}-databricks-role"
  path = "/service-roles/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DatabricksAssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::414351767826:root"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            # Validation em variables.tf garante que nao e vazio.
            "sts:ExternalId" = var.databricks_external_id
          }
        }
      },
      {
        Sid    = "SelfAssumingRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:role/service-roles/${var.project_name}-databricks-role"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Purpose = "databricks-cross-account"
  }
}

# --- Pipeline Agent Role ---
# Para execucoes automatizadas (Lambda, ECS, etc.) que rodam scripts do pipeline
resource "aws_iam_role" "pipeline_agent" {
  name = "${var.project_name}-pipeline-agent-role"
  path = "/service-roles/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEC2Assume"
        Effect = "Allow"
        Principal = {
          Service = [
            "ec2.amazonaws.com",
            "lambda.amazonaws.com",
            "ecs-tasks.amazonaws.com"
          ]
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Purpose = "pipeline-agent-execution"
  }
}

# --- Instance Profile para EC2 (se necessario) ---
resource "aws_iam_instance_profile" "pipeline_agent" {
  name = "${var.project_name}-pipeline-agent-profile"
  role = aws_iam_role.pipeline_agent.name
}

# --- Attach policies aos roles ---
resource "aws_iam_role_policy_attachment" "databricks_s3" {
  role       = aws_iam_role.databricks_cross_account.name
  policy_arn = aws_iam_policy.databricks_s3_access.arn
}

resource "aws_iam_role_policy_attachment" "agent_s3" {
  role       = aws_iam_role.pipeline_agent.name
  policy_arn = aws_iam_policy.pipeline_s3_access.arn
}

resource "aws_iam_role_policy_attachment" "agent_secrets" {
  role       = aws_iam_role.pipeline_agent.name
  policy_arn = aws_iam_policy.pipeline_secrets_read.arn
}
