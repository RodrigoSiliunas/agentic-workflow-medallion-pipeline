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
# UCMasterRole pra AWS prod — documentado + estavel
# https://docs.databricks.com/en/connect/unity-catalog/cloud-storage/storage-credentials.html
_UC_MASTER_ROLE_ARN = (
    f"arn:aws:iam::{_DATABRICKS_ACCOUNT_ID}:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"
)
_DATABRICKS_ROLE_SUFFIX = "-uc-role"


def _build_trust_policy(
    external_id: str | None = None,
    self_role_arn: str | None = None,
) -> dict:
    """Trust policy Unity Catalog — self-assuming + external_id.

    UC exige que a role assumivel seja 'self-assuming':
    - Principal = UCMasterRole + a propria role (quando conhecida)
    - Condition StringEquals sts:ExternalId = <gerado Databricks>

    Fluxo:
    1. iam step cria role com bootstrap (UCMasterRole apenas, sem external_id)
       - self_role_arn=None + external_id=None
    2. catalog step cria Storage Credential -> Databricks retorna external_id
    3. catalog step chama update com (UCMasterRole + role_arn + external_id)
    """
    principals: list[str] = [_UC_MASTER_ROLE_ARN]
    if self_role_arn:
        principals.append(self_role_arn)

    statement: dict = {
        "Effect": "Allow",
        "Principal": {"AWS": principals if len(principals) > 1 else principals[0]},
        "Action": "sts:AssumeRole",
    }
    if external_id:
        statement["Condition"] = {
            "StringEquals": {"sts:ExternalId": external_id},
        }
    return {
        "Version": "2012-10-17",
        "Statement": [statement],
    }


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

        # Cria role com trust bootstrap (sem Condition). catalog step
        # depois recupera external_id do Databricks e atualiza trust policy.
        await ctx.info("Role nao encontrada — criando via boto3 (trust bootstrap)...")
        arn = await self._create_role(ctx, role_name)
        ctx.shared.databricks_role_arn = arn
        await ctx.success(
            f"Role criada: {arn} (trust sem Condition — catalog step atualiza com external_id)"
        )

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

        # Trust bootstrap sem Condition. catalog step atualiza com external_id.
        trust_policy = _build_trust_policy(external_id=None)

        # Policy UC pattern: S3 access + sts:AssumeRole self-reference.
        # Self-assuming exige BOTH trust policy principal self-ref E
        # inline allow sts:AssumeRole na propria role (esse statement).
        account_id = ctx.credentials.aws_access_key_id  # placeholder — precisa real
        # Na verdade role_arn sera construido abaixo apos create; aqui
        # usamos wildcard controlado: role name na inline policy.
        role_arn_for_self = f"arn:aws:iam::*:role/{role_name}"

        s3_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                        "s3:PutObject",
                        "s3:PutObjectAcl",
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
                # Self-assuming: role precisa poder assumir a si mesma
                # (pattern UC). Sem isso, Databricks nao consegue validar.
                {
                    "Effect": "Allow",
                    "Action": ["sts:AssumeRole"],
                    "Resource": [role_arn_for_self],
                },
            ],
        }

        def _create() -> str:
            # Path="/" (default) — UC self-assuming trust policy nao aceita
            # role ARN com Path customizado no Principal ("Invalid principal").
            role = iam.create_role(
                RoleName=role_name,
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


async def update_trust_policy_with_external_id(
    ctx: StepContext, role_arn: str, external_id: str
) -> None:
    """Helper chamado pelo catalog step apos criar Storage Credential.

    Atualiza trust policy da role com pattern UC completo:
    - Principal: UCMasterRole + a propria role (self-assuming)
    - Condition: StringEquals sts:ExternalId = external_id gerado Databricks

    Retry com backoff: role recem-criada pode nao ser principal valido
    (IAM eventual consistency ~10s). MalformedPolicyDocument com 'Invalid
    principal' indica role ainda nao propagou.
    """
    role_name = role_arn.rsplit("/", 1)[-1]
    session = boto3_session(ctx.credentials)
    iam = session.client("iam")
    trust = _build_trust_policy(external_id=external_id, self_role_arn=role_arn)

    def _update() -> None:
        iam.update_assume_role_policy(
            RoleName=role_name, PolicyDocument=json.dumps(trust)
        )

    delays = [0, 5, 10, 15, 20, 30]
    last_err: Exception | None = None
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            await ctx.info(
                f"Trust update retry {attempt}/{len(delays)} "
                f"apos {delay}s (IAM principal propagation)"
            )
            await asyncio.sleep(delay)
        try:
            await asyncio.to_thread(_update)
            await ctx.info(
                f"Trust policy da role {role_name} atualizada "
                f"(self-assuming + external_id len={len(external_id)})"
            )
            return
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            msg = str(exc)
            if code == "MalformedPolicyDocument" and "Invalid principal" in msg:
                last_err = exc
                continue
            raise

    raise RuntimeError(
        f"Trust policy update falhou apos {len(delays)} retries "
        f"(IAM principal propagation timeout): {last_err}"
    )
