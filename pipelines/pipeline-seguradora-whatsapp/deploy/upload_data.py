"""Upload do Parquet Bronze para S3 data lake.

Uso: python deploy/upload_data.py <local_parquet_path>

Requer:
  - AWS CLI configurado (aws configure) OU env vars AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
  - Env var S3_BUCKET (default: flowertex-medallion-datalake)
"""

import os
import sys

import boto3


def upload(local_path: str):
    bucket = os.environ.get("S3_BUCKET", "flowertex-medallion-datalake")
    region = os.environ.get("AWS_REGION", "us-east-2")

    s3 = boto3.client("s3", region_name=region)

    filename = os.path.basename(local_path)
    s3_key = f"bronze/{filename}"

    file_size = os.path.getsize(local_path)
    print(f"Uploading {local_path} -> s3://{bucket}/{s3_key}")
    print(f"  Size: {file_size / 1024 / 1024:.1f} MB")

    s3.upload_file(local_path, bucket, s3_key)

    print(f"Upload completo: s3://{bucket}/{s3_key}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python deploy/upload_data.py <path_to_parquet>")
        sys.exit(1)
    upload(sys.argv[1])
