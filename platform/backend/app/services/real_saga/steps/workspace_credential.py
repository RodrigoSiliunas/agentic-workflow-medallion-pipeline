"""Step `workspace_credential` — cria IAM role cross-account + DB credentials config.

Segundo step novo da saga completa. Cria role que o Databricks Account usa
pra lancar EC2/EBS/etc na conta AWS do cliente (cross-account access).

Diferente do IamStep (que cria UC role pra S3). Este cria a role que o
workspace usa pra provisionar clusters.

Trust policy exige:
- Databricks root principal (414351767826:root)
- Self-assuming (pra UC chained assume)
- Condition sts:ExternalId = account_id

Policies:
- EC2 + IAM (provisionar clusters)
- S3 root bucket (workspace root bucket access)

POST /api/2.0/accounts/{id}/credentials registra no Databricks.
"""

from __future__ import annotations

import asyncio
import json

import boto3
import httpx

from app.services.real_saga.base import StepContext
from app.services.real_saga.registry import register_saga_step

_DATABRICKS_AWS_ACCOUNT = "414351767826"


@register_saga_step("workspace_credential")
class WorkspaceCredentialStep:
    step_id = "workspace_credential"

    async def execute(self, ctx: StepContext) -> None:
        env = ctx.env_vars()
        account_id = env.get("databricks_account_id", "")
        oauth_client_id = env.get("databricks_oauth_client_id", "")
        oauth_secret = env.get("databricks_oauth_secret", "")

        # Modo workspace existing: usuario passou IDs prontos no wizard,
        # nao precisa criar credentials nem role.
        if env.get("workspace_mode") == "existing":
            existing_id = env.get("databricks_credentials_id", "")
            if existing_id:
                ctx.shared.databricks_credentials_id = existing_id
                await ctx.info(
                    f"workspace_mode=existing — reutilizando credentials_id={existing_id}"
                )
            else:
                await ctx.warn(
                    "workspace_mode=existing sem databricks_credentials_id — "
                    "workspace_provision vai puxar do workspace_id direto"
                )
            return

        # Root bucket vem do step s3 (precedencia: shared > env_var legado)
        root_bucket = ctx.shared.workspace_root_bucket or env.get(
            "workspace_root_bucket", ""
        )

        if not all([account_id, oauth_client_id, oauth_secret, root_bucket]):
            await ctx.warn(
                "Skipping workspace_credential — Account OAuth ou root bucket ausente "
                "(passe credenciais OAuth + rode step s3 antes pra popular root_bucket)"
            )
            return

        project = env.get("project_name", "medallion-pipeline")
        role_name = f"{project}-databricks-xaccount-role"

        session = boto3.Session(
            aws_access_key_id=ctx.credentials.require("aws_access_key_id"),
            aws_secret_access_key=ctx.credentials.require("aws_secret_access_key"),
            region_name=ctx.credentials.require("aws_region"),
        )
        iam = session.client("iam")

        role_arn = await asyncio.to_thread(
            self._ensure_role, iam, role_name, account_id, root_bucket
        )
        await ctx.info(f"Cross-account role: {role_arn}")
        ctx.shared.databricks_xaccount_role_arn = role_arn

        creds_id = await self._register_databricks_credentials(
            ctx, account_id, oauth_client_id, oauth_secret,
            f"{project}-credentials", role_arn,
        )
        ctx.shared.databricks_credentials_id = creds_id
        await ctx.success(f"DB credentials: {creds_id}")

    @staticmethod
    def _ensure_role(iam, role_name: str, account_id: str, root_bucket: str) -> str:
        trust = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"AWS": [
                    f"arn:aws:iam::{_DATABRICKS_AWS_ACCOUNT}:root",
                ]},
                "Action": "sts:AssumeRole",
                "Condition": {"StringEquals": {"sts:ExternalId": account_id}},
            }],
        }
        try:
            r = iam.get_role(RoleName=role_name)
            role_arn = r["Role"]["Arn"]
            # Update trust
            iam.update_assume_role_policy(
                RoleName=role_name, PolicyDocument=json.dumps(trust)
            )
        except iam.exceptions.NoSuchEntityException:
            r = iam.create_role(
                Path="/service-roles/",
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust),
            )
            role_arn = r["Role"]["Arn"]

        # EC2 + IAM policy (minimal Databricks requirements)
        ec2_pol = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:*", "iam:CreateServiceLinkedRole", "iam:PutRolePolicy",
                    ],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": "iam:PassRole",
                    "Resource": f"arn:aws:iam::{role_arn.split(':')[4]}:role/*",
                },
            ],
        }
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="DatabricksEC2Policy",
            PolicyDocument=json.dumps(ec2_pol),
        )

        # S3 root bucket policy
        s3_pol = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
                    "s3:ListBucket", "s3:GetBucketLocation",
                    "s3:ListBucketMultipartUploads", "s3:AbortMultipartUpload",
                    "s3:ListMultipartUploadParts",
                ],
                "Resource": [
                    f"arn:aws:s3:::{root_bucket}",
                    f"arn:aws:s3:::{root_bucket}/*",
                ],
            }],
        }
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="DatabricksS3RootPolicy",
            PolicyDocument=json.dumps(s3_pol),
        )
        return role_arn

    @staticmethod
    async def _register_databricks_credentials(
        ctx: StepContext,
        account_id: str,
        client_id: str,
        client_secret: str,
        creds_name: str,
        role_arn: str,
    ) -> str:
        async with httpx.AsyncClient(timeout=30.0) as c:
            token_resp = await c.post(
                f"https://accounts.cloud.databricks.com/oidc/accounts/{account_id}/v1/token",
                auth=(client_id, client_secret),
                data={"grant_type": "client_credentials", "scope": "all-apis"},
            )
            token_resp.raise_for_status()
            token = token_resp.json()["access_token"]

            list_resp = await c.get(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/credentials",
                headers={"Authorization": f"Bearer {token}"},
            )
            list_resp.raise_for_status()
            for cred in list_resp.json() or []:
                if cred.get("credentials_name") == creds_name:
                    return cred["credentials_id"]

            create_resp = await c.post(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/credentials",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "credentials_name": creds_name,
                    "aws_credentials": {
                        "sts_role": {"role_arn": role_arn}
                    },
                },
            )
            create_resp.raise_for_status()
            return create_resp.json()["credentials_id"]
