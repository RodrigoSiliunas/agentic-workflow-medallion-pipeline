# =============================================================================
# Variaveis — 01-foundation
# =============================================================================

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Nome do projeto (usado em tags e nomes de recursos)"
  type        = string
  default     = "medallion-pipeline"
}

variable "environment" {
  description = "Ambiente (production, staging, dev)"
  type        = string
  default     = "production"
}

variable "databricks_account_id" {
  description = "Databricks account ID (para IAM trust policy)"
  type        = string
  default     = ""
}

variable "databricks_external_id" {
  description = "External ID fornecido pelo Databricks Quickstart (AWS Account Setup)"
  type        = string
  default     = ""
}

variable "create_pipeline_user" {
  description = "Criar IAM user para pipeline CI/CD (programmatic access)"
  type        = bool
  default     = true
}

variable "bucket_name" {
  description = "Nome do S3 bucket do data lake"
  type        = string
  default     = "namastex-medallion-datalake"
}

variable "databricks_root_bucket" {
  description = "Nome do S3 bucket para Databricks root storage (assets, libs, logs)"
  type        = string
  default     = "namastex-databricks-root"
}
