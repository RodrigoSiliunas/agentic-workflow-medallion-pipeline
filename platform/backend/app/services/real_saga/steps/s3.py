"""Step `s3` — verifica ou cria buckets do datalake e do workspace root.

Cria DOIS buckets:
- **datalake** (nome do wizard, ex: `flowertex-medallion-datalake`): bronze/silver/gold
- **workspace root** (default `{datalake}-root` ou override do advanced): DBFS root,
  cluster logs, init scripts compartilhados. Necessario pra customer-managed VPC
  do Databricks. Recebe bucket policy permitindo Databricks AWS account principal.

Fast path: boto3 `head_bucket`. Se o bucket ja existe, loga e pula.
Slow path: boto3 `create_bucket` com versionamento + encryption + public access block.

Nota: a versao anterior usava Terraform pra criar o bucket, mas o modulo
`infra/aws/02-datalake` tem dependency de `terraform_remote_state` no
01-foundation que nao funciona em workspace isolado. boto3 direto e mais
simples e nao depende de state cross-module.

O nome do bucket vem de `config.env_vars["s3_bucket"]` (preenchido pelo wizard).
Override do root bucket vem de `env_vars["workspace_root_bucket"]` (advanced).
"""

from __future__ import annotations

import asyncio
import json

from botocore.exceptions import ClientError

from app.services.real_saga.aws_client import boto3_session
from app.services.real_saga.base import StepContext
from app.services.real_saga.registry import register_saga_step

# Conta AWS oficial do Databricks pro plano commercial. Documentado em
# https://docs.databricks.com/en/admin/workspace/cross-account-iam.html
_DATABRICKS_AWS_ACCOUNT = "414351767826"


@register_saga_step("s3")
class S3Step:
    step_id = "s3"

    async def compensate(self, ctx: StepContext) -> None:
        """Rollback: deleta APENAS buckets criados nesta saga (track via shared).

        Buckets adopted (ja existiam antes) NAO sao deletados — evita destruir
        dados de outros pipelines. Tolera bucket ja ausente.
        """
        created = list(ctx.shared.s3_buckets_created)
        if not created:
            await ctx.info("compensate(s3): nenhum bucket criado nesta saga — skip")
            return

        session = boto3_session(ctx.credentials)
        s3 = session.client("s3")

        for bucket in created:
            def _delete(b: str = bucket) -> bool:
                try:
                    paginator = s3.get_paginator("list_object_versions")
                    to_delete: list[dict] = []
                    for page in paginator.paginate(Bucket=b):
                        for obj in page.get("Versions", []) or []:
                            to_delete.append(
                                {"Key": obj["Key"], "VersionId": obj.get("VersionId")}
                            )
                        for obj in page.get("DeleteMarkers", []) or []:
                            to_delete.append(
                                {"Key": obj["Key"], "VersionId": obj.get("VersionId")}
                            )
                        if to_delete:
                            s3.delete_objects(
                                Bucket=b,
                                Delete={"Objects": to_delete[:1000], "Quiet": True},
                            )
                            to_delete = to_delete[1000:]
                    s3.delete_bucket(Bucket=b)
                    return True
                except ClientError as exc:
                    code = exc.response.get("Error", {}).get("Code", "")
                    if code in ("NoSuchBucket", "404"):
                        return False
                    raise

            try:
                deleted = await asyncio.to_thread(_delete)
            except Exception as exc:  # noqa: BLE001
                await ctx.warn(f"compensate(s3) falhou em deletar {bucket}: {exc}")
                continue

            if deleted:
                await ctx.info(f"compensate(s3): bucket {bucket} removido")
            else:
                await ctx.info(f"compensate(s3): bucket {bucket} ja nao existia")

    async def execute(self, ctx: StepContext) -> None:
        bucket_name = _resolve_bucket_name(ctx)
        region = ctx.credentials.require("aws_region")

        # Datalake bucket
        await ctx.info(f"Verificando S3 bucket datalake '{bucket_name}' em {region}")
        if await self._bucket_exists(ctx, bucket_name):
            await ctx.info("Datalake bucket ja existe — reutilizando.")
        else:
            await ctx.info("Datalake bucket nao encontrado — criando via boto3...")
            await self._create_bucket(ctx, bucket_name, region)
            ctx.shared.s3_buckets_created.append(bucket_name)

        # Sample data: SEMPRE verificar — bucket pode existir vazio
        # (deploy anterior abortou ou aws-nuke removeu objetos sem o bucket).
        await self._upload_sample_data(ctx, bucket_name)

        ctx.shared.s3_bucket = bucket_name
        ctx.shared.s3_bucket_url = f"s3://{bucket_name}"

        # Workspace root bucket — default `{datalake}-root` ou override
        root_bucket = _resolve_root_bucket_name(ctx, bucket_name)
        await ctx.info(f"Verificando workspace root bucket '{root_bucket}'")
        if await self._bucket_exists(ctx, root_bucket):
            await ctx.info("Root bucket ja existe — reutilizando.")
        else:
            await ctx.info("Root bucket nao encontrado — criando via boto3...")
            await self._create_bucket(ctx, root_bucket, region, databricks_root=True)
            ctx.shared.s3_buckets_created.append(root_bucket)

        # Bucket policy idempotente pra permitir Databricks AWS account
        await self._apply_databricks_root_policy(ctx, root_bucket)
        ctx.shared.workspace_root_bucket = root_bucket
        await ctx.success(
            f"Buckets prontos: datalake=s3://{bucket_name}, root=s3://{root_bucket}"
        )

    @staticmethod
    async def _bucket_exists(ctx: StepContext, bucket_name: str) -> bool:
        session = boto3_session(ctx.credentials)
        s3 = session.client("s3")

        def _check() -> bool:
            try:
                s3.head_bucket(Bucket=bucket_name)
                return True
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("404", "NoSuchBucket", "NotFound"):
                    return False
                if code == "403":
                    return True
                raise

        return await asyncio.to_thread(_check)

    @staticmethod
    async def _create_bucket(
        ctx: StepContext,
        bucket_name: str,
        region: str,
        databricks_root: bool = False,
    ) -> None:
        session = boto3_session(ctx.credentials)
        s3 = session.client("s3")

        def _create() -> None:
            # Criar bucket (us-east-1 nao aceita LocationConstraint)
            create_args: dict = {"Bucket": bucket_name}
            if region != "us-east-1":
                create_args["CreateBucketConfiguration"] = {
                    "LocationConstraint": region
                }
            s3.create_bucket(**create_args)

            # Versionamento (necessario pra Delta Lake time travel)
            s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={"Status": "Enabled"},
            )

            # Encryption SSE-S3
            s3.put_bucket_encryption(
                Bucket=bucket_name,
                ServerSideEncryptionConfiguration={
                    "Rules": [
                        {
                            "ApplyServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "AES256"
                            },
                            "BucketKeyEnabled": True,
                        }
                    ]
                },
            )

            # Bloquear acesso publico
            s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )

            # Datalake recebe pastas medallion. Root bucket so precisa
            # da raiz limpa — Databricks gerencia DBFS/cluster-logs/init-scripts.
            if not databricks_root:
                for prefix in (
                    "bronze/", "silver/", "gold/", "pipeline/", "checkpoints/",
                ):
                    s3.put_object(Bucket=bucket_name, Key=prefix, Body=b"")

        await asyncio.to_thread(_create)
        kind = "root bucket" if databricks_root else "bucket"
        await ctx.success(
            f"{kind.capitalize()} criado: s3://{bucket_name} "
            f"(versioning=on, encryption=AES256, public_access=blocked)"
        )

    @staticmethod
    async def _apply_databricks_root_policy(
        ctx: StepContext, bucket_name: str
    ) -> None:
        """Aplica bucket policy permitindo Databricks AWS account principal.

        Necessario pro workspace customer-managed VPC funcionar — Databricks
        precisa Get/Put/List no bucket pra DBFS root + cluster logs.
        Idempotente: PutBucketPolicy substitui policy existente.
        """
        session = boto3_session(ctx.credentials)
        s3 = session.client("s3")

        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "DatabricksWorkspaceRootAccess",
                "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{_DATABRICKS_AWS_ACCOUNT}:root"},
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:ListBucketMultipartUploads",
                    "s3:AbortMultipartUpload",
                    "s3:ListMultipartUploadParts",
                ],
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*",
                ],
            }],
        }

        def _put() -> None:
            s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))

        await asyncio.to_thread(_put)
        await ctx.info(f"Bucket policy aplicada em '{bucket_name}' (Databricks principal)")


    @staticmethod
    async def _upload_sample_data(ctx: StepContext, bucket_name: str) -> None:
        """Upload do parquet de sample. Idempotente: skip se key ja existe."""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[6]
        sample = (
            repo_root / "pipelines/pipeline-seguradora-whatsapp"
            / "data/conversations_bronze.parquet"
        )
        if not sample.exists():
            await ctx.warn(
                f"Sample parquet nao encontrado em {sample} — bronze rodara sem dados."
            )
            return

        session = boto3_session(ctx.credentials)
        s3 = session.client("s3")
        key = f"bronze/{sample.name}"

        def _exists() -> bool:
            try:
                s3.head_object(Bucket=bucket_name, Key=key)
                return True
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("404", "NoSuchKey", "NotFound"):
                    return False
                raise

        already = await asyncio.to_thread(_exists)
        if already:
            await ctx.info(f"Sample data ja em s3://{bucket_name}/{key} — skip")
            return

        size_mb = sample.stat().st_size / 1024 / 1024

        def _upload() -> None:
            s3.upload_file(str(sample), bucket_name, key)

        await ctx.info(f"Uploading sample data ({size_mb:.1f} MB) -> s3://{bucket_name}/{key}")
        await asyncio.to_thread(_upload)
        await ctx.success(f"Sample data uploaded: {key}")


def _resolve_bucket_name(ctx: StepContext) -> str:
    env = ctx.env_vars()
    bucket = env.get("s3_bucket") or env.get("bucket_name")
    if not bucket:
        raise ValueError(
            "S3 bucket nao definido — o wizard/template deve passar `s3_bucket` em env_vars."
        )
    return bucket


def _resolve_root_bucket_name(ctx: StepContext, datalake_bucket: str) -> str:
    """Root bucket name: override do advanced ou derivado `{datalake}-root`.

    Mantem buckets separados (recommended Databricks) sem exigir input extra
    do usuario casual. Override existe pra naming convention da empresa.
    """
    env = ctx.env_vars()
    override = (env.get("workspace_root_bucket") or "").strip()
    if override:
        return override
    return f"{datalake_bucket}-root"
