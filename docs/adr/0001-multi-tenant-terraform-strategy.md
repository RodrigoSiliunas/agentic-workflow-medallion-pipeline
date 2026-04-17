# ADR 0001 — Estratégia multi-tenant para infra AWS

**Status**: proposta · **Data**: 2026-04-16 · **Contexto track**: T3

## Problema

O produto está evoluindo para marketplace de pipelines com deploy "one-click" por empresa. `infra/aws/` hoje descreve uma única conta (`flowertex`) e `terraform_remote_state` aponta para state local — inviabiliza N clientes sem refactor.

3 alternativas em jogo:

- **(A)** S3 backend `workspace`-per-company
- **(B)** Módulo Terraform parametrizado + invocação via Terragrunt/wrapper
- **(C)** Deprecar Terraform standalone — backend Python + `boto3` saga faz tudo

## Opção A — Terraform workspace-per-company

**Como funciona**: um único código em `infra/aws/`, state S3 particionado por workspace (`terraform workspace new acme-corp`). Variáveis por workspace em `env/acme-corp.tfvars`.

**Pros**:
- Menor delta de código — reusa o que já existe
- State encryption + lock herdados do 00-backend
- `terraform plan` por workspace roda em CI

**Cons**:
- Workspaces compartilham provider config — account switching exige assume-role por workspace
- Drift entre workspaces vira pesadelo rápido (sem "parent" óbvio)
- Scaling ruim — 100+ workspaces ficam lentos pra listar/migrar
- Não casa bem com o fluxo Celery/API que o produto já usa pra deployments

## Opção B — Módulo parametrizado + Terragrunt

**Como funciona**: `infra/aws/modules/` com as abstrações reusáveis. Cada empresa tem diretório próprio (`infra/aws/envs/acme-corp/`) que instancia os módulos. Terragrunt (ou wrapper shell) orquestra.

**Pros**:
- Isolamento explícito por empresa
- Fácil fazer diff/audit por cliente
- Compatível com remote state S3 (key por env)

**Cons**:
- Adiciona dependência (Terragrunt) + nova camada mental
- Onboard de nova empresa = PR no repo — frustra fluxo "one-click"
- Lifecycle de destroy/update exige humano rodando `terragrunt apply` — contraria visão do produto

## Opção C — Deprecar Terraform standalone

**Como funciona**: manter `00-backend/01-foundation/02-datalake` apenas como **template de referência** (documentação viva + guard rail pra tfsec). O runtime de deploy usa `boto3` + `databricks-sdk` já presente em `platform/backend/app/services/real_saga/`, onde os passos (S3/IAM/Secret Scope/Catalog) são idempotentes, versionados e compensáveis.

**Pros**:
- Alinha com visão de produto "one-click por empresa via UI"
- Saga runtime já existe (T4 vai amadurecer) — sem duplicação
- Multi-tenant natural — cada request tem `company_id` + credenciais próprias
- Dynamic rollback (compensating actions) > Terraform destroy
- Remove fricção de usuário final ter que entender Terraform

**Cons**:
- Perde declaratividade (drift entre desired state e reality)
- Visibilidade de infra muda pra painel próprio (não `terraform show`)
- tfsec/checkov não cobrem mais — precisa policy engine próprio

## Decisão

**Opção C** — deprecar Terraform como provisioner em produção; manter apenas como template de referência (`infra/aws/`).

Racional:
1. A visão de produto exige provisioning programático via API. `terraform apply` do humano não escala pra "cliente se cadastra → infra sobe em 5min".
2. Saga em `platform/backend/app/services/real_saga/` já vai ganhar compensating actions em **T4**. Aproveitar esse investimento.
3. O valor que Terraform agregaria (declaratividade + drift detection) pode ser obtido com um scheduled `boto3` audit que compara `desired_spec` de cada pipeline com a realidade da conta.

### Terraform continua servindo

- Desenvolvimento do **flowertex** (conta interna) — infra estável, Terraform ok
- Template de referência: código em `infra/aws/` vira a "spec canônica" que o runtime Python precisa implementar
- CI `ci-infra.yml` garante que o template continua válido + passa tfsec/tflint

### Consequências imediatas

- T3 fecha fortalecendo o template de referência (KMS, TLS, secrets, SG)
- T4 assume a responsabilidade de provisionar infra real em produção
- Não implementamos Terragrunt nem workspaces
- `data "terraform_remote_state"` em `02-datalake/data.tf` permanece para uso interno

### Revisão

Reavaliar em 6 meses (~2026-10) quando T4 estiver maduro e tivermos 3+ pipelines no ar via saga. Se a paridade com o template Terraform estiver longe, reconsiderar opção B.
