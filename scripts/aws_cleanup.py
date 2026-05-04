"""One-shot cleanup das resources criados pela saga no AWS.

Deleta:
- S3 buckets: flowertex-medallion-datalake, flowertex-medallion-datalake-root
  (versioned — limpa todos versions + delete markers antes de delete_bucket)
- IAM role: medallion-pipeline-uc-role (detach policies + delete role)

Preserva:
- databricks-workspace-stack-* (workspace ativo)
- databricks-compute/storage-role-* (workspace cross-account)
"""

from __future__ import annotations

import boto3

s3 = boto3.client("s3", region_name="us-east-1")
iam = boto3.client("iam")

BUCKETS = ["flowertex-medallion-datalake", "flowertex-medallion-datalake-root"]
ROLES = ["medallion-pipeline-uc-role"]


def empty_bucket(bucket: str) -> int:
    paginator = s3.get_paginator("list_object_versions")
    deleted = 0
    for page in paginator.paginate(Bucket=bucket):
        keys = []
        for v in page.get("Versions") or []:
            keys.append({"Key": v["Key"], "VersionId": v["VersionId"]})
        for d in page.get("DeleteMarkers") or []:
            keys.append({"Key": d["Key"], "VersionId": d["VersionId"]})
        for i in range(0, len(keys), 1000):
            batch = keys[i:i + 1000]
            if batch:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
                deleted += len(batch)
    return deleted


def delete_role(role_name: str) -> None:
    try:
        for p in iam.list_role_policies(RoleName=role_name).get("PolicyNames", []):
            iam.delete_role_policy(RoleName=role_name, PolicyName=p)
            print(f"  inline policy {p} removed")
        for ap in iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", []):
            iam.detach_role_policy(RoleName=role_name, PolicyArn=ap["PolicyArn"])
            print(f"  attached policy {ap['PolicyArn']} detached")
        iam.delete_role(RoleName=role_name)
        print(f"  ROLE DELETED: {role_name}")
    except iam.exceptions.NoSuchEntityException:
        print(f"  role nao existe: {role_name}")


for b in BUCKETS:
    print(f"== {b} ==")
    try:
        n = empty_bucket(b)
        print(f"  {n} versions deleted")
        s3.delete_bucket(Bucket=b)
        print(f"  BUCKET DELETED: {b}")
    except s3.exceptions.NoSuchBucket:
        print("  bucket nao existe")
    except Exception as e:
        print(f"  FAIL: {e}")

for r in ROLES:
    print(f"== {r} ==")
    delete_role(r)

print("\nDONE")
