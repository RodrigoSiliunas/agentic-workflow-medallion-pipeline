"""Step `s3` — verifica ou cria o bucket do datalake.

Fast path: boto3 `head_bucket`. Se o bucket ja existe, loga e pula.
Slow path: boto3 `create_bucket` com versionamento + encryption + public access block.

Nota: a versao anterior usava Terraform pra criar o bucket, mas o modulo
`infra/aws/02-datalake` tem dependency de `terraform_remote_state` no
01-foundation que nao funciona em workspace isolado. boto3 direto e mais
simples e nao depende de state cross-module.

O nome do bucket vem de `config.env_vars["s3_bucket"]` (preenchido pelo wizard).
"""

from __future__ import annotations

import asyncio

from botocore.exceptions import ClientError

from app.services.real_saga.aws_client import boto3_session
from app.services.real_saga.base import StepContext


class S3Step:
    step_id = "s3"

    async def execute(self, ctx: StepContext) -> None:
        bucket_name = _resolve_bucket_name(ctx)
        region = ctx.credentials.require("aws_region")
        await ctx.info(f"Verificando S3 bucket '{bucket_name}' em {region}")

        if await self._bucket_exists(ctx, bucket_name):
            await ctx.info("Bucket ja existe — reutilizando.")
            ctx.shared.s3_bucket = bucket_name
            ctx.shared.s3_bucket_url = f"s3://{bucket_name}"
            return

        await ctx.info("Bucket nao encontrado — criando via boto3...")
        await self._create_bucket(ctx, bucket_name, region)
        ctx.shared.s3_bucket = bucket_name
        ctx.shared.s3_bucket_url = f"s3://{bucket_name}"

        # Upload sample data se existir localmente
        await self._upload_sample_data(ctx, bucket_name)

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
    async def _create_bucket(ctx: StepContext, bucket_name: str, region: str) -> None:
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

            # Criar pastas-placeholder (como o Terraform faz)
            for prefix in ("bronze/", "silver/", "gold/", "pipeline/", "checkpoints/"):
                s3.put_object(Bucket=bucket_name, Key=prefix, Body=b"")

        await asyncio.to_thread(_create)
        await ctx.success(
            f"Bucket criado: s3://{bucket_name} "
            f"(versioning=on, encryption=AES256, public_access=blocked)"
        )


    @staticmethod
    async def _upload_sample_data(ctx: StepContext, bucket_name: str) -> None:
        """Upload do parquet de sample se existir localmente."""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[6]
        sample = (
            repo_root / "pipelines/pipeline-seguradora-whatsapp"
            / "data/conversations_bronze.parquet"
        )
        if not sample.exists():
            await ctx.info("Sem dados de sample locais — pule ou faca upload manual")
            return

        session = boto3_session(ctx.credentials)
        s3 = session.client("s3")
        key = f"bronze/{sample.name}"
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
