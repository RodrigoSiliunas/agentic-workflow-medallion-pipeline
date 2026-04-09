"""Setup completo do Unity Catalog para o pipeline Medallion.

Fluxo:
  1. Storage Credential (IAM Role -> Databricks)
  2. External Location (S3 bucket)
  3. Catalog 'medallion'
  4. Schemas: bronze, silver, gold, pipeline

Tudo com logica IF NOT EXISTS — erro se existir com config diferente.

Uso: python deploy/setup_catalog.py

Requer env vars:
  DATABRICKS_HOST    — URL do workspace (ex: https://dbc-xxx.cloud.databricks.com)
  DATABRICKS_TOKEN   — Personal Access Token
  AWS_IAM_ROLE_ARN   — ARN da role cross-account do Databricks (output do Terraform)
  S3_BUCKET_URL      — URL do bucket (ex: s3://namastex-medallion-datalake)
"""

import os
import sys

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import AwsIamRoleRequest


# ============================================================
# CONFIG
# ============================================================
CATALOG_NAME = "medallion"
CREDENTIAL_NAME = "medallion-s3-credential"
LOCATION_NAME = "medallion-datalake"
SCHEMAS = ["bronze", "silver", "gold", "pipeline"]


def get_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"ERRO: env var '{key}' nao definida")
        sys.exit(1)
    return val


def step_storage_credential(w: WorkspaceClient, role_arn: str):
    """Cria Storage Credential que permite Databricks acessar S3 via IAM Role."""
    print("\n[1/4] Storage Credential")

    existing = list(w.storage_credentials.list())
    for cred in existing:
        if cred.name == CREDENTIAL_NAME:
            # Verificar se config eh igual
            if cred.aws_iam_role and cred.aws_iam_role.role_arn == role_arn:
                print(f"  '{CREDENTIAL_NAME}' ja existe com mesmo role_arn — skip")
                return
            else:
                print(f"  ERRO: '{CREDENTIAL_NAME}' existe com config DIFERENTE!")
                print(f"    Existente: {cred.aws_iam_role}")
                print(f"    Esperado:  role_arn={role_arn}")
                print("  Remova manualmente ou use outro nome.")
                sys.exit(1)

    w.storage_credentials.create(
        name=CREDENTIAL_NAME,
        aws_iam_role=AwsIamRoleRequest(role_arn=role_arn),
        comment="Acesso S3 para pipeline Medallion (Terraform-managed IAM Role)",
    )
    print(f"  '{CREDENTIAL_NAME}' criado (role: {role_arn})")


def step_external_location(w: WorkspaceClient, s3_url: str):
    """Cria External Location apontando para o bucket S3."""
    print("\n[2/4] External Location")

    existing = list(w.external_locations.list())
    for loc in existing:
        if loc.name == LOCATION_NAME:
            if loc.url.rstrip("/") == s3_url.rstrip("/"):
                print(f"  '{LOCATION_NAME}' ja existe com mesmo URL — skip")
                return
            else:
                print(f"  ERRO: '{LOCATION_NAME}' existe com URL DIFERENTE!")
                print(f"    Existente: {loc.url}")
                print(f"    Esperado:  {s3_url}")
                sys.exit(1)

    w.external_locations.create(
        name=LOCATION_NAME,
        url=s3_url,
        credential_name=CREDENTIAL_NAME,
        comment="Data lake S3 do pipeline Medallion",
    )
    print(f"  '{LOCATION_NAME}' criado ({s3_url})")


def step_catalog(w: WorkspaceClient, s3_url: str):
    """Cria o catalog 'medallion' no Unity Catalog com managed location no S3."""
    print("\n[3/4] Catalog")

    try:
        w.catalogs.create(
            name=CATALOG_NAME,
            comment="Pipeline Medallion - WhatsApp Insurance Analytics",
            storage_root=s3_url,
        )
        print(f"  Catalog '{CATALOG_NAME}' criado (storage: {s3_url})")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"  Catalog '{CATALOG_NAME}' ja existe — skip")
        else:
            raise


def step_schemas(w: WorkspaceClient):
    """Cria os schemas bronze/silver/gold/pipeline."""
    print("\n[4/4] Schemas")

    for schema in SCHEMAS:
        try:
            w.schemas.create(
                name=schema,
                catalog_name=CATALOG_NAME,
                comment=f"Camada {schema} do pipeline Medallion",
            )
            print(f"  Schema '{CATALOG_NAME}.{schema}' criado")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  Schema '{CATALOG_NAME}.{schema}' ja existe — skip")
            else:
                raise


def setup():
    host = get_env("DATABRICKS_HOST")
    token = get_env("DATABRICKS_TOKEN")
    role_arn = get_env("AWS_IAM_ROLE_ARN")
    s3_url = get_env("S3_BUCKET_URL")

    print("=" * 60)
    print("Databricks Unity Catalog Setup — Medallion Pipeline")
    print("=" * 60)
    print(f"  Host:     {host}")
    print(f"  Role ARN: {role_arn}")
    print(f"  S3 URL:   {s3_url}")

    w = WorkspaceClient(host=host, token=token)
    user = w.current_user.me()
    print(f"  User:     {user.user_name}")

    step_storage_credential(w, role_arn)
    step_external_location(w, s3_url)
    step_catalog(w, s3_url)
    step_schemas(w)

    print("\n" + "=" * 60)
    print("Setup completo!")
    print("=" * 60)
    print(f"  Catalog:  {CATALOG_NAME}")
    for s in SCHEMAS:
        print(f"  Schema:   {CATALOG_NAME}.{s}")
    print(f"  S3:       {s3_url}")
    print("\nProximo: python deploy/upload_data.py <parquet_path>")


if __name__ == "__main__":
    setup()
