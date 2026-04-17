# =============================================================================
# Data Sources — Referencia ao 01-foundation
# =============================================================================

# Leitura do state do 01-foundation.
#
# Default: backend local — funciona antes da migracao.
# Apos migrar ambos os modulos pro S3, trocar para o bloco comentado
# abaixo removendo o local.
data "terraform_remote_state" "foundation" {
  backend = "local"

  config = {
    path = "${path.module}/../01-foundation/terraform.tfstate"
  }
}

# Versao S3 (pos-migracao):
# data "terraform_remote_state" "foundation" {
#   backend = "s3"
#   config = {
#     bucket         = "flowertex-terraform-state"
#     key            = "foundation/terraform.tfstate"
#     region         = "us-east-2"
#     dynamodb_table = "flowertex-terraform-state-lock"
#     encrypt        = true
#   }
# }

# Shortcuts para outputs do foundation
locals {
  databricks_role_arn = data.terraform_remote_state.foundation.outputs.databricks_role_arn
  pipeline_agent_arn  = data.terraform_remote_state.foundation.outputs.pipeline_agent_role_arn
  sg_pipeline_id      = data.terraform_remote_state.foundation.outputs.sg_pipeline_services_id
  datalake_kms_arn    = data.terraform_remote_state.foundation.outputs.datalake_kms_key_arn
}
