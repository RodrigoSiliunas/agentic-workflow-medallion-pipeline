# =============================================================================
# Data Sources — Referencia ao 01-foundation
# =============================================================================

# Leitura do state do 01-foundation (local backend)
data "terraform_remote_state" "foundation" {
  backend = "local"

  config = {
    path = "${path.module}/../01-foundation/terraform.tfstate"
  }
}

# Shortcuts para outputs do foundation
locals {
  databricks_role_arn = data.terraform_remote_state.foundation.outputs.databricks_role_arn
  pipeline_agent_arn  = data.terraform_remote_state.foundation.outputs.pipeline_agent_role_arn
  sg_pipeline_id      = data.terraform_remote_state.foundation.outputs.sg_pipeline_services_id
}
