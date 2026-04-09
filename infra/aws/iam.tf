# =============================================================================
# IAM Policy para Databricks acessar o S3
# NOTA: A IAM Role sera criada pelo Databricks Quickstart (CloudFormation).
# Esta policy pode ser anexada manualmente se necessario.
# =============================================================================

resource "aws_iam_policy" "databricks_s3_access" {
  name        = "DatabricksExternalLocationPolicy"
  description = "Permite Databricks acessar o data lake S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DatabricksS3ReadWrite"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = [
          aws_s3_bucket.datalake.arn,
          "${aws_s3_bucket.datalake.arn}/*",
        ]
      },
      {
        Sid    = "DatabricksS3List"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = aws_s3_bucket.datalake.arn
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}
