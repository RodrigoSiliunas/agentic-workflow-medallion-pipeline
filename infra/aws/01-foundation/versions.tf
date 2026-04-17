# =============================================================================
# Terraform + Provider — 01-foundation
# =============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — rodar 00-backend primeiro e depois migrar.
  # Passo-a-passo:
  #   1. cd ../00-backend && terraform apply
  #   2. Descomentar o bloco abaixo
  #   3. cd ../01-foundation && terraform init -migrate-state
  # backend "s3" {
  #   bucket         = "flowertex-terraform-state"
  #   key            = "foundation/terraform.tfstate"
  #   region         = "us-east-2"
  #   dynamodb_table = "flowertex-terraform-state-lock"
  #   encrypt        = true
  #   kms_key_id     = "alias/flowertex-tfstate"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      Team        = "data-engineering"
      ManagedBy   = "terraform"
      Module      = "foundation"
    }
  }
}

# Account ID dinamico — evita hardcoding
data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}
