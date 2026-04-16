# =============================================================================
# Outputs — 01-foundation
# Consumidos pelo 02-datalake via terraform_remote_state
# =============================================================================

# --- IAM Roles ---
output "databricks_role_arn" {
  description = "ARN da role cross-account do Databricks"
  value       = aws_iam_role.databricks_cross_account.arn
}

output "databricks_role_name" {
  description = "Nome da role cross-account do Databricks"
  value       = aws_iam_role.databricks_cross_account.name
}

output "pipeline_agent_role_arn" {
  description = "ARN da role do pipeline agent"
  value       = aws_iam_role.pipeline_agent.arn
}

output "pipeline_agent_instance_profile_arn" {
  description = "ARN do instance profile do pipeline agent"
  value       = aws_iam_instance_profile.pipeline_agent.arn
}

# --- IAM Policies ---
output "databricks_s3_policy_arn" {
  description = "ARN da policy de acesso S3 para Databricks"
  value       = aws_iam_policy.databricks_s3_access.arn
}

output "pipeline_s3_policy_arn" {
  description = "ARN da policy de acesso S3 para pipeline"
  value       = aws_iam_policy.pipeline_s3_access.arn
}

# --- IAM User (pipeline) ---
output "pipeline_user_arn" {
  description = "ARN do IAM user do pipeline"
  value       = var.create_pipeline_user ? aws_iam_user.pipeline[0].arn : ""
}

output "pipeline_user_name" {
  description = "Nome do IAM user do pipeline"
  value       = var.create_pipeline_user ? aws_iam_user.pipeline[0].name : ""
}

output "pipeline_credentials_secret_arn" {
  description = "ARN do secret com credenciais do pipeline user"
  value       = var.create_pipeline_user ? aws_secretsmanager_secret.pipeline_credentials[0].arn : ""
}

# --- Security Groups ---
output "sg_pipeline_services_id" {
  description = "ID do security group para pipeline services"
  value       = aws_security_group.pipeline_services.id
}

output "sg_backend_api_id" {
  description = "ID do security group para backend API"
  value       = aws_security_group.backend_api.id
}

output "sg_database_id" {
  description = "ID do security group para database"
  value       = aws_security_group.database.id
}

# --- VPC ---
output "vpc_id" {
  description = "ID da VPC default"
  value       = data.aws_vpc.default.id
}

output "vpc_cidr" {
  description = "CIDR block da VPC default"
  value       = data.aws_vpc.default.cidr_block
}

# --- Secrets ---
output "secret_arns" {
  description = "Map de ARNs dos secrets criados"
  value = {
    anthropic    = aws_secretsmanager_secret.anthropic_api_key.arn
    github       = aws_secretsmanager_secret.github_token.arn
    databricks   = aws_secretsmanager_secret.databricks_token.arn
    database     = aws_secretsmanager_secret.database_url.arn
    backend_keys = aws_secretsmanager_secret.backend_keys.arn
  }
}

# --- KMS ---
output "datalake_kms_key_arn" {
  description = "ARN da KMS CMK usada no datalake (consumido por 02-datalake)"
  value       = aws_kms_key.datalake.arn
}

output "secrets_kms_key_arn" {
  description = "ARN da KMS CMK dos Secrets Manager"
  value       = aws_kms_key.secrets.arn
}
