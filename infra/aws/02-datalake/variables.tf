# =============================================================================
# Variaveis — 02-datalake
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

variable "bucket_name" {
  description = "Nome do S3 bucket do data lake"
  type        = string
  default     = "flowertex-medallion-datalake"
}
