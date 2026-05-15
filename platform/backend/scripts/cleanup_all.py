#!/usr/bin/env python3
"""Cleanup completo — reseta AWS + Databricks pra testar deploy from scratch.

Uso:
    # Dry-run (mostra o que seria deletado, sem deletar nada)
    python scripts/cleanup_all.py --dry-run

    # Executa de verdade (pede confirmacao interativa)
    python scripts/cleanup_all.py

    # Pula confirmacao (CI/scripted)
    python scripts/cleanup_all.py --yes

Requer:
    - AWS credentials configuradas (~/.aws/credentials ou env vars)
    - DATABRICKS_HOST + DATABRICKS_TOKEN no .env ou env vars

O script le credenciais do .env na raiz do backend automaticamente.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Carrega .env files (raiz do repo + backend) antes de usar env vars
for _env_path in [
    Path(__file__).parent.parent.parent.parent / ".env",  # repo root
    Path(__file__).parent.parent / ".env",  # platform/backend
]:
    if _env_path.exists():
        for _line in _env_path.read_text().splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip())

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "")

# Recursos AWS pra deletar
S3_BUCKETS = ["flowertex-medallion-datalake", "flowertex-databricks-root"]
IAM_ROLE_PREFIX = "medallion-pipeline-"
IAM_INSTANCE_PROFILE_PREFIX = "medallion-pipeline-"
SECRETS_PREFIX = "medallion-pipeline/"

# Recursos Databricks pra deletar
DATABRICKS_JOB_NAMES = ["medallion_pipeline_whatsapp", "workflow_observer_agent"]
DATABRICKS_SECRET_SCOPE = "medallion-pipeline"
DATABRICKS_CATALOG = "medallion"
DATABRICKS_REPO_SUBSTRING = "agentic-workflow-medallion-pipeline"


def _green(text: str) -> str:
    return f"\033[92m{text}\033[0m"


def _red(text: str) -> str:
    return f"\033[91m{text}\033[0m"


def _yellow(text: str) -> str:
    return f"\033[93m{text}\033[0m"


def _header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# AWS CLEANUP
# ---------------------------------------------------------------------------
def cleanup_s3(session: boto3.Session, dry_run: bool) -> None:
    _header("S3 Buckets")
    s3 = session.resource("s3")
    s3_client = session.client("s3")

    for bucket_name in S3_BUCKETS:
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except ClientError:
            print(f"  {_yellow('SKIP')} {bucket_name} (nao existe)")
            continue

        bucket = s3.Bucket(bucket_name)
        obj_count = sum(1 for _ in bucket.objects.limit(1000))
        print(f"  {_red('DELETE')} {bucket_name} ({obj_count}+ objetos)")

        if dry_run:
            continue

        # Deletar todas as versoes + delete markers (required pra buckets versionados)
        bucket.object_versions.delete()
        bucket.objects.all().delete()
        bucket.delete()
        print(f"    {_green('OK')} bucket deletado")


def cleanup_iam(session: boto3.Session, dry_run: bool) -> None:
    _header("IAM Roles + Policies + Instance Profiles")
    iam = session.client("iam")

    # Instance profiles
    try:
        profiles = iam.list_instance_profiles()["InstanceProfiles"]
        for profile in profiles:
            if profile["InstanceProfileName"].startswith(IAM_INSTANCE_PROFILE_PREFIX):
                name = profile["InstanceProfileName"]
                print(f"  {_red('DELETE')} instance profile: {name}")
                if not dry_run:
                    # Remover roles do profile antes de deletar
                    for role in profile.get("Roles", []):
                        iam.remove_role_from_instance_profile(
                            InstanceProfileName=name,
                            RoleName=role["RoleName"],
                        )
                    iam.delete_instance_profile(InstanceProfileName=name)
                    print(f"    {_green('OK')}")
    except ClientError as e:
        print(f"  {_yellow('WARN')} instance profiles: {e}")

    # Roles (precisa detach policies e delete inline policies antes)
    try:
        paginator = iam.get_paginator("list_roles")
        for page in paginator.paginate():
            for role in page["Roles"]:
                if not role["RoleName"].startswith(IAM_ROLE_PREFIX):
                    continue
                role_name = role["RoleName"]
                print(f"  {_red('DELETE')} role: {role_name}")
                if dry_run:
                    continue

                # Detach managed policies
                attached = iam.list_attached_role_policies(RoleName=role_name)[
                    "AttachedPolicies"
                ]
                for pol in attached:
                    iam.detach_role_policy(
                        RoleName=role_name, PolicyArn=pol["PolicyArn"]
                    )

                # Deletar políticas inline
                inline = iam.list_role_policies(RoleName=role_name)["PolicyNames"]
                for pol_name in inline:
                    iam.delete_role_policy(RoleName=role_name, PolicyName=pol_name)

                iam.delete_role(RoleName=role_name)
                print(f"    {_green('OK')}")
    except ClientError as e:
        print(f"  {_yellow('WARN')} roles: {e}")

    # Managed policies (custom, nao AWS-managed)
    try:
        paginator = iam.get_paginator("list_policies")
        for page in paginator.paginate(Scope="Local"):
            for policy in page["Policies"]:
                if IAM_ROLE_PREFIX in policy["PolicyName"]:
                    arn = policy["Arn"]
                    print(f"  {_red('DELETE')} policy: {policy['PolicyName']}")
                    if not dry_run:
                        # Deletar versoes nao-default antes de deletar a policy
                        versions = iam.list_policy_versions(PolicyArn=arn)[
                            "Versions"
                        ]
                        for v in versions:
                            if not v["IsDefaultVersion"]:
                                iam.delete_policy_version(
                                    PolicyArn=arn, VersionId=v["VersionId"]
                                )
                        iam.delete_policy(PolicyArn=arn)
                        print(f"    {_green('OK')}")
    except ClientError as e:
        print(f"  {_yellow('WARN')} policies: {e}")


def cleanup_secrets(session: boto3.Session, dry_run: bool) -> None:
    _header("Secrets Manager")
    sm = session.client("secretsmanager")

    try:
        paginator = sm.get_paginator("list_secrets")
        for page in paginator.paginate():
            for secret in page["SecretList"]:
                name = secret["Name"]
                if not name.startswith(SECRETS_PREFIX):
                    continue
                print(f"  {_red('DELETE')} {name}")
                if not dry_run:
                    sm.delete_secret(
                        SecretId=name, ForceDeleteWithoutRecovery=True
                    )
                    print(f"    {_green('OK')}")
    except ClientError as e:
        print(f"  {_yellow('WARN')} secrets: {e}")


# ---------------------------------------------------------------------------
# DATABRICKS CLEANUP
# ---------------------------------------------------------------------------
def cleanup_databricks(dry_run: bool) -> None:
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
        print(f"\n  {_yellow('SKIP')} Databricks (sem DATABRICKS_HOST/TOKEN configurado)")
        return

    from databricks.sdk import WorkspaceClient
    from databricks.sdk.errors import NotFound, ResourceDoesNotExist

    w = WorkspaceClient(host=DATABRICKS_HOST, token=DATABRICKS_TOKEN)

    # Jobs
    _header("Databricks Jobs")
    try:
        for job in w.jobs.list():
            if job.settings and job.settings.name in DATABRICKS_JOB_NAMES:
                print(f"  {_red('DELETE')} job: {job.settings.name} (id={job.job_id})")
                if not dry_run:
                    w.jobs.delete(job_id=job.job_id)
                    print(f"    {_green('OK')}")
    except Exception as e:
        print(f"  {_yellow('WARN')} jobs: {e}")

    # Repos
    _header("Databricks Repos")
    try:
        for repo in w.repos.list():
            if repo.path and DATABRICKS_REPO_SUBSTRING in repo.path:
                print(f"  {_red('DELETE')} repo: {repo.path} (id={repo.id})")
                if not dry_run:
                    w.repos.delete(repo_id=repo.id)
                    print(f"    {_green('OK')}")
    except Exception as e:
        print(f"  {_yellow('WARN')} repos: {e}")

    # Secret scope
    _header("Databricks Secret Scope")
    try:
        scopes = list(w.secrets.list_scopes())
        matched = [s for s in scopes if s.name == DATABRICKS_SECRET_SCOPE]
        if matched:
            print(f"  {_red('DELETE')} scope: {DATABRICKS_SECRET_SCOPE}")
            if not dry_run:
                w.secrets.delete_scope(scope=DATABRICKS_SECRET_SCOPE)
                print(f"    {_green('OK')}")
        else:
            print(f"  {_yellow('SKIP')} scope '{DATABRICKS_SECRET_SCOPE}' nao existe")
    except Exception as e:
        print(f"  {_yellow('WARN')} secret scope: {e}")

    # Unity Catalog (schemas + catalog)
    _header("Databricks Unity Catalog")
    try:
        # Listar e dropar schemas do catalog
        schemas = list(w.schemas.list(catalog_name=DATABRICKS_CATALOG))
        for schema in schemas:
            if schema.name in ("default", "information_schema"):
                continue
            full_name = f"{DATABRICKS_CATALOG}.{schema.name}"
            print(f"  {_red('DELETE')} schema: {full_name}")
            if not dry_run:
                try:
                    # CASCADE deleta todas as tabelas/views/volumes dentro
                    w.schemas.delete(full_name_arg=full_name, force=True)
                    print(f"    {_green('OK')}")
                except Exception as e:
                    print(f"    {_yellow('WARN')} {e}")

        # Dropar o catalog
        print(f"  {_red('DELETE')} catalog: {DATABRICKS_CATALOG}")
        if not dry_run:
            try:
                w.catalogs.delete(name=DATABRICKS_CATALOG, force=True)
                print(f"    {_green('OK')}")
            except (NotFound, ResourceDoesNotExist):
                print(f"    {_yellow('SKIP')} catalog nao existe")
            except Exception as e:
                print(f"    {_yellow('WARN')} {e}")
    except (NotFound, ResourceDoesNotExist):
        print(f"  {_yellow('SKIP')} catalog '{DATABRICKS_CATALOG}' nao existe")
    except Exception as e:
        print(f"  {_yellow('WARN')} catalog: {e}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset completo: deleta AWS + Databricks pra deploy from scratch."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria deletado sem executar",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Pula confirmacao interativa",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  CLEANUP ALL — AWS + Databricks Reset")
    print(f"{'='*60}")
    print(f"  Regiao AWS:     {AWS_REGION}")
    print(f"  Databricks:     {DATABRICKS_HOST or '(nao configurado)'}")
    mode = "DRY-RUN (nada sera deletado)" if args.dry_run else "REAL"
    print(f"  Modo:           {mode if args.dry_run else _red(mode)}")

    if not args.dry_run and not args.yes:
        print(f"\n  {_red('ATENCAO')}: Isso vai deletar TODOS os recursos listados acima.")
        confirm = input("  Digitar 'CONFIRMAR' pra continuar: ")
        if confirm.strip() != "CONFIRMAR":
            print("  Cancelado.")
            sys.exit(0)

    session = boto3.Session(region_name=AWS_REGION)

    # AWS cleanup
    cleanup_s3(session, args.dry_run)
    cleanup_iam(session, args.dry_run)
    cleanup_secrets(session, args.dry_run)

    # Databricks cleanup
    cleanup_databricks(args.dry_run)

    print(f"\n{'='*60}")
    if args.dry_run:
        print(f"  {_yellow('DRY-RUN completo')} — nenhum recurso foi deletado.")
        print("  Rode sem --dry-run pra executar de verdade.")
    else:
        print(f"  {_green('CLEANUP completo')} — ambiente pronto pra deploy from scratch.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
