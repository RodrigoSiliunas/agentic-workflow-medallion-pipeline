# AWS Infrastructure — Medallion Pipeline

Terraform organizado em 3 modulos. O `00-backend` roda uma vez (bootstrap);
`01-foundation` e `02-datalake` rodam toda vez que mudarmos a infra.

> **Status arquitetural**: Terraform vira template de referencia em
> producao. O runtime real de deploy multi-tenant usa saga Python +
> `boto3` (ver `docs/adr/0001-multi-tenant-terraform-strategy.md`).

## Estrutura

```
infra/aws/
├── 00-backend/        # S3 + DynamoDB remote state + KMS key (bootstrap)
│   ├── versions.tf
│   ├── kms.tf
│   ├── s3.tf             # Bucket tfstate + Deny SecureTransport=false
│   ├── dynamodb.tf       # Lock table (SSE-KMS + PITR)
│   └── outputs.tf
│
├── 01-foundation/     # IAM, Security Groups, Secrets, KMS CMKs
│   ├── versions.tf       # Backend S3 block (commented — aplicar apos 00)
│   ├── variables.tf      # databricks_external_id tem validation obrigatoria
│   ├── kms.tf            # CMK datalake + CMK secrets (rotation anual)
│   ├── iam_users.tf      # Pipeline CI/CD user
│   ├── iam_roles.tf      # DatabricksRole + PipelineAgentRole
│   ├── iam_policies.tf
│   ├── security.tf       # SGs (ingress 8000 REMOVIDO)
│   ├── secrets.tf        # Secrets com KMS CMK + recovery_window=7
│   ├── databricks_root.tf # SSE-KMS + Deny SecureTransport=false
│   └── terraform.tfvars  # NAO contem databricks_external_id
│
└── 02-datalake/       # S3 data lake com lifecycle
    ├── versions.tf
    ├── data.tf           # terraform_remote_state -> 01-foundation
    ├── s3.tf             # SSE-KMS (CMK do 01-foundation) + Deny TLS=false
    └── outputs.tf
```

## Segurança (T3)

- **Remote state** S3 + DynamoDB lock, SSE-KMS, versionado. Evita state local comprometivel + race condition em apply concorrente.
- **CMK dedicadas** — `alias/namastex-datalake`, `alias/namastex-secrets`, `alias/namastex-tfstate`. Rotation anual automatica.
- **TLS enforce** — `Deny aws:SecureTransport=false` em todos os buckets.
- **Secrets** — KMS CMK + `recovery_window_in_days=7` (evita delete acidental).
- **ExternalID** — `variable.databricks_external_id` tem `validation { length > 0 }`. Valor vem de `terraform.tfvars.local` (gitignored) ou `TF_VAR_databricks_external_id`.
- **SG backend API** — porta 8000 `0.0.0.0/0` removida. Apenas 80 (redirect) + 443.
- **CI** — `.github/workflows/ci-infra.yml` roda `fmt -check`, `validate`, `tflint`, `tfsec` (SARIF) em todo push/PR que toca `infra/**`.

## Pre-requisitos

```bash
winget install Hashicorp.Terraform
winget install Amazon.AWSCLI
aws configure  # Access Key + Secret Key + Region us-east-2
```

## Execucao

### Primeira vez — bootstrap do backend

```bash
# 0. Backend (S3 tfstate + DynamoDB lock) — UMA VEZ POR CONTA
cd infra/aws/00-backend
terraform init
terraform apply
# Anote os outputs (backend_bucket, lock_table)
```

### Depois — infra do projeto

```bash
# Obrigatorio: set env var com External ID do Databricks
export TF_VAR_databricks_external_id="<UUID gerado pelo Databricks Quickstart>"
# OU copie terraform.tfvars.example pra terraform.tfvars.local (gitignored)

# 1. Foundation (IAM, Security Groups, Secrets, KMS)
cd infra/aws/01-foundation
# Opcional na primeira vez: descomentar backend "s3" em versions.tf
# e rodar `terraform init -migrate-state`
terraform init
terraform plan
terraform apply

# 2. Data Lake (S3 bucket SSE-KMS)
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
