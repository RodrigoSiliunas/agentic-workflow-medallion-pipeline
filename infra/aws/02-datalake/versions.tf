# =============================================================================
# Terraform + Provider — 02-datalake
# =============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — rodar 00-backend primeiro. Mesmo setup do 01-foundation,
  # so muda a key.
  # backend "s3" {
  #   bucket         = "flowertex-terraform-state"
  #   key            = "datalake/terraform.tfstate"
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
      Module      = "datalake"
    }
  }
}
