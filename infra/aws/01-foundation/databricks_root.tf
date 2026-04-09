# =============================================================================
# S3 Databricks Root Storage — assets, libs, logs do workspace
# =============================================================================

resource "aws_s3_bucket" "databricks_root" {
  bucket = var.databricks_root_bucket

  tags = {
    Purpose = "databricks-root-storage"
  }
}

resource "aws_s3_bucket_versioning" "databricks_root" {
  bucket = aws_s3_bucket.databricks_root.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "databricks_root" {
  bucket = aws_s3_bucket.databricks_root.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Bucket policy para Databricks (gerada pelo console Databricks)
resource "aws_s3_bucket_policy" "databricks_root" {
  bucket = aws_s3_bucket.databricks_root.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GrantDatabricksAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::414351767826:root"
        }
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = [
          aws_s3_bucket.databricks_root.arn,
          "${aws_s3_bucket.databricks_root.arn}/*",
        ]
        Condition = {
          StringEquals = {
            "aws:PrincipalTag/DatabricksAccountId" = [
              var.databricks_external_id
            ]
          }
        }
      }
    ]
  })
}
