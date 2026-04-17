"""Step `iam` — verifica se a IAM role do Databricks existe.

Se existe: loga e prossegue. Se nao: cria uma role basica com trust policy
pro Databricks e attach de S3 access.

Nota: a versao original usava Terraform pra criar roles+policies complexas.
Por pragmatismo, usamos boto3 direto com uma policy inline simples. O
pipeline funciona tanto com a role (cross-account) quanto sem ela (usando
credentials diretas do IAM user via secret scope).
"""

from __future__ import annotations

import asyncio
import json

from botocore.exceptions import ClientError

from app.services.real_saga.aws_client import boto3_session
from app.services.real_saga.base import StepContext
from app.services.real_saga.registry import register_saga_step

_DATABRICKS_ACCOUNT_ID = "414351767826"
_DATABRICKS_ROLE_SUFFIX = "-databricks-role"


@register_saga_step("iam")
class IamStep:
    step_id = "iam"

    async def compensate(self, ctx: StepContext) -> None:
        """Rollback: deleta a role + inline policy se criadas nesta saga.

        Tolera role ja ausente. NAO deleta role que foi reutilizada
        (shared.databricks_role_arn setado sem passar pelo create path
        se role ja existia — neste caso compensate faz skip).
        """
        project_name = ctx.env_vars().get("project_name", "medallion-pipeline")
        role_name = f"{project_name}{_DATABRICKS_ROLE_SUFFIX}"

        session = boto3_session(ctx.credentials)
        iam = session.client("iam")

        def _delete() -> bool:
            try:
                policies = iam.list_role_policies(RoleName=role_name).get(
                    "PolicyNames", []
                )
                for name in policies:
                    iam.delete_role_policy(RoleName=role_name, PolicyName=name)
                attached = iam.list_attached_role_policies(
                    RoleName=role_name
                ).get("AttachedPolicies", [])
                for pol in attached:
                    iam.detach_role_policy(
                        RoleName=role_name, PolicyArn=pol["PolicyArn"]
                    )
                iam.delete_role(RoleName=role_name)
                return True
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchEntity", "NoSuchEntityException"):
                    return False
                raise

        try:
            deleted = await asyncio.to_thread(_delete)
        except Exception as exc:  # noqa: BLE001
            await ctx.warn(f"compensate(iam) falhou em deletar {role_name}: {exc}")
            return

        if deleted:
            await ctx.info(f"compensate(iam): role {role_name} removida")
        else:
            await ctx.info(f"compensate(iam): role {role_name} ja nao existia")

    async def execute(self, ctx: StepContext) -> None:
        project_name = ctx.env_vars().get("project_name", "medallion-pipeline")
        role_name = f"{project_name}{_DATABRICKS_ROLE_SUFFIX}"

        await ctx.info(f"Verificando IAM role '{role_name}'")

        existing = await self._get_role(ctx, role_name)
        if existing:
            await ctx.info(f"IAM role ja existe: {existing}")
            ctx.shared.databricks_role_arn = existing
            return

        await ctx.info("Role nao encontrada — criando via boto3...")
        arn = await self._create_role(ctx, role_name)
        ctx.shared.databricks_role_arn = arn
        await ctx.success(f"Role criada: {arn}")

    @staticmethod
    async def _get_role(ctx: StepContext, role_name: str) -> str | None:
        session = boto3_session(ctx.credentials)
        iam = session.client("iam")

        def _check() -> str | None:
            try:
                resp = iam.get_role(RoleName=role_name)
                return resp["Role"]["Arn"]
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchEntity", "NoSuchEntityException"):
                    return None
                raise

        return await asyncio.to_thread(_check)

    @staticmethod
    async def _create_role(ctx: StepContext, role_name: str) -> str:
        session = boto3_session(ctx.credentials)
        iam = session.client("iam")
        bucket_name = ctx.shared.s3_bucket or ctx.env_vars().get("s3_bucket", "*")

        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": f"arn:aws:iam::{_DATABRICKS_ACCOUNT_ID}:root"
                    },
                    "Action": "sts:AssumeRole",
                    "Condition": {},
                }
            ],
        }

        s3_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket",
                        "s3:GetBucketLocation",
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{bucket_name}/*",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:ListAllMyBuckets"],
                    "Resource": "*",
                },
            ],
        }

        def _create() -> str:
            role = iam.create_role(
                RoleName=role_name,
                Path="/service-roles/",
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Databricks cross-account role for Unity Catalog + S3",
                Tags=[
                    {"Key": "Project", "Value": "medallion-pipeline"},
                    {"Key": "ManagedBy", "Value": "flowertex-platform"},
                ],
            )
            arn = role["Role"]["Arn"]

            iam.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-s3-access",
                PolicyDocument=json.dumps(s3_policy),
            )

            return arn

        return await asyncio.to_thread(_create)
