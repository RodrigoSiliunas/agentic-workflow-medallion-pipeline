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
  description = <<-EOT
    External ID fornecido pelo Databricks Quickstart (AWS Account Setup).
    Obrigatorio — sem ele a trust policy da role cross-account nao tem
    barreira contra confused deputy. Ver AWS docs: IAM External ID.

    NAO commitar valor real. Preencher via:
      - `terraform.tfvars.local` (gitignored) — dev local
      - SSM Parameter / env var `TF_VAR_databricks_external_id` — CI
  EOT
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.databricks_external_id) > 0
    error_message = "databricks_external_id nao pode ser vazio. Ver comentario do variable."
  }
}

variable "create_pipeline_user" {
  description = "Criar IAM user para pipeline CI/CD (programmatic access)"
  type        = bool
  default     = true
}

variable "bucket_name" {
  description = "Nome do S3 bucket do data lake"
  type        = string
  default     = "flowertex-medallion-datalake"
}

variable "databricks_root_bucket" {
  description = "Nome do S3 bucket para Databricks root storage (assets, libs, logs)"
  type        = string
  default     = "flowertex-databricks-root"
}
