output "bucket_name" {
  description = "Nome do S3 bucket"
  value       = aws_s3_bucket.datalake.id
}

output "bucket_arn" {
  description = "ARN do S3 bucket"
  value       = aws_s3_bucket.datalake.arn
}

output "bucket_region" {
  description = "Regiao do bucket"
  value       = aws_s3_bucket.datalake.region
}

output "bucket_url" {
  description = "URL S3 para uso no Databricks"
  value       = "s3://${aws_s3_bucket.datalake.id}"
}

output "iam_policy_arn" {
  description = "ARN da IAM policy para Databricks"
  value       = aws_iam_policy.databricks_s3_access.arn
}
