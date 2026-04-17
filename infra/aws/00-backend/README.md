# 00-backend — Terraform remote state bootstrap

Cria o bucket S3 + tabela DynamoDB que vão hospedar o state remoto dos módulos `01-foundation` e `02-datalake`.

**Chicken-and-egg**: este módulo usa state **local** (não pode usar o backend S3 antes de criar o bucket). Só precisa rodar uma vez por conta.

## Bootstrap

```bash
cd infra/aws/00-backend
terraform init
terraform apply
```

Saída esperada:

- `aws_s3_bucket.terraform_state` — `flowertex-terraform-state`
- `aws_dynamodb_table.terraform_locks` — `flowertex-terraform-state-lock`

## Migração dos outros módulos

Depois que o backend existir:

```bash
# 01-foundation
cd ../01-foundation
# Descomentar block `backend "s3"` em versions.tf
terraform init -migrate-state

# 02-datalake
cd ../02-datalake
# Descomentar block `backend "s3"` em versions.tf
terraform init -migrate-state
```

`terraform` vai detectar o state local e oferecer migrar pro S3. Responda `yes`.

## O que este módulo cria

| Recurso | Nome | Função |
|---------|------|--------|
| S3 bucket | `flowertex-terraform-state` | guarda arquivos `.tfstate` |
| Versioning | Enabled | recuperar state corrompido |
| SSE-KMS | `alias/flowertex-tfstate` | encryption em repouso |
| Public access block | todos true | bloqueia exposição acidental |
| Bucket policy | Deny `aws:SecureTransport=false` | força TLS |
| DynamoDB table | `flowertex-terraform-state-lock` | locking concorrente |

## Variáveis

- `aws_region` (default `us-east-2`)
- `backend_bucket_name` (default `flowertex-terraform-state`)
- `lock_table_name` (default `flowertex-terraform-state-lock`)

## Cleanup (não recomendado em produção)

```bash
terraform destroy
```

Só funciona se **nenhum outro módulo** estiver usando o backend. Remova `versions.tf:backend "s3"` dos módulos consumidores e rode `terraform init -migrate-state` invertendo para local antes.
