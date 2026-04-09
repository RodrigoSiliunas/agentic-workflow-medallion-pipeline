# AWS Infrastructure — Medallion Pipeline

Terraform organizado em 2 modulos executados em sequencia.

## Estrutura

```
infra/aws/
├── 01-foundation/    # IAM users, roles, security groups, secrets
│   ├── versions.tf
│   ├── variables.tf
│   ├── iam_users.tf      # Pipeline CI/CD user + credentials no Secrets Manager
│   ├── iam_roles.tf      # DatabricksRole + PipelineAgentRole
│   ├── iam_policies.tf   # S3 access, Secrets read, STS
│   ├── security.tf       # Security groups (pipeline, backend, database)
│   ├── secrets.tf        # Secrets Manager (Anthropic, GitHub, Databricks, DB, JWT)
│   ├── outputs.tf
│   └── terraform.tfvars
│
└── 02-datalake/      # S3 bucket com lifecycle, encryption, bucket policy
    ├── versions.tf
    ├── variables.tf
    ├── data.tf           # terraform_remote_state -> 01-foundation
    ├── s3.tf             # Bucket + lifecycle + folder prefixes
    ├── outputs.tf
    └── terraform.tfvars
```

## Pre-requisitos

```bash
winget install Hashicorp.Terraform
winget install Amazon.AWSCLI
aws configure  # Access Key + Secret Key + Region us-east-2
```

## Execucao

```bash
# 1. Foundation (IAM, Security Groups, Secrets)
cd infra/aws/01-foundation
terraform init
terraform plan
terraform apply

# 2. Data Lake (S3 bucket) — depende do 01-foundation
cd ../02-datalake
terraform init
terraform plan
terraform apply
```

## Apos Terraform

1. Preencher secrets via AWS Console ou CLI:
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id medallion-pipeline/anthropic-api-key \
     --secret-string '{"api_key":"sk-ant-..."}'
   ```

2. Copiar o `databricks_role_arn` do output do 01-foundation
3. Usar no Databricks Quickstart (External Location) para linkar o S3

## Notas

- **01-foundation** cria a base de IAM/seguranca. Executar PRIMEIRO.
- **02-datalake** referencia o state do 01 via `terraform_remote_state` (backend local).
- Para migrar para S3 backend, descomentar o bloco `backend "s3"` em versions.tf.
- O `databricks_external_id` deve ser preenchido apos iniciar o Quickstart no Databricks.
