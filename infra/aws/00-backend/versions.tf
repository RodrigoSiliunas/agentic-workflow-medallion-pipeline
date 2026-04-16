# =============================================================================
# Terraform + Provider — 00-backend (bootstrap remote state)
# =============================================================================
#
# Este modulo NAO usa backend remoto — chicken-and-egg: ele cria o
# bucket que hospedaria o state. Backend local fica em
# ./terraform.tfstate.
# =============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "medallion-pipeline"
      Environment = "production"
      Team        = "data-engineering"
      ManagedBy   = "terraform"
      Module      = "backend-bootstrap"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}
