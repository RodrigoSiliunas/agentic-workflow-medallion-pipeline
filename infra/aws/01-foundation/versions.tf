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

  # Estado local — migrar para S3 backend depois do bootstrap
  # backend "s3" {
  #   bucket = "namastex-terraform-state"
  #   key    = "foundation/terraform.tfstate"
  #   region = "us-east-2"
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
