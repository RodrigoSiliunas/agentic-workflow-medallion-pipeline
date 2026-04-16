# =============================================================================
# Variaveis — 00-backend
# =============================================================================

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "backend_bucket_name" {
  description = "Nome do S3 bucket que hospeda os arquivos tfstate"
  type        = string
  default     = "namastex-terraform-state"
}

variable "lock_table_name" {
  description = "Nome da tabela DynamoDB usada para lock concorrente"
  type        = string
  default     = "namastex-terraform-state-lock"
}
