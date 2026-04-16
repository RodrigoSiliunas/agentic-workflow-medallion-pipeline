aws_region            = "us-east-2"
project_name          = "medallion-pipeline"
environment           = "production"
databricks_account_id = ""
# databricks_external_id vem de terraform.tfvars.local (gitignored) ou
# da env var TF_VAR_databricks_external_id — nao commitar aqui.
# Valor anterior foi exposto em git historico — ROTACIONAR no Databricks.
create_pipeline_user = true
bucket_name          = "namastex-medallion-datalake"
