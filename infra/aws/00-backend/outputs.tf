# =============================================================================
# Outputs — 00-backend
# =============================================================================

output "backend_bucket" {
  description = "Nome do bucket que hospeda os tfstate"
  value       = aws_s3_bucket.terraform_state.bucket
}

output "backend_bucket_arn" {
  description = "ARN do bucket de state"
  value       = aws_s3_bucket.terraform_state.arn
}

output "lock_table" {
  description = "Nome da tabela DynamoDB de lock"
  value       = aws_dynamodb_table.terraform_locks.name
}

output "kms_key_arn" {
  description = "ARN da KMS key usada em repouso no state"
  value       = aws_kms_key.tfstate.arn
}

output "backend_config_example" {
  description = "Bloco backend S3 pronto pra colar nos modulos consumidores"
  value       = <<-EOT
    backend "s3" {
      bucket         = "${aws_s3_bucket.terraform_state.bucket}"
      key            = "<module-name>/terraform.tfstate"
      region         = "${var.aws_region}"
      dynamodb_table = "${aws_dynamodb_table.terraform_locks.name}"
      encrypt        = true
      kms_key_id     = "${aws_kms_key.tfstate.arn}"
    }
  EOT
}
