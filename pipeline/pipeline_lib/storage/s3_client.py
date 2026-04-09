"""S3 Data Lake client para notebooks Databricks.

Usa dbutils.secrets para credenciais AWS (multi-tenant ready).
Cada tenant tem seu proprio secret scope com aws-access-key-id,
aws-secret-access-key, aws-region e s3-bucket.

Uso no notebook:
    from pipeline_lib.storage import S3Lake
    lake = S3Lake(dbutils, scope="medallion-pipeline")
    lake.download("bronze/data.parquet", "/tmp/data.parquet")
    lake.upload("/tmp/result.parquet", "silver/result.parquet")
"""

import os
import tempfile

import boto3


class S3Lake:
    """Client S3 usando credenciais do Databricks Secrets."""

    def __init__(self, dbutils, scope: str = "medallion-pipeline"):
        self.dbutils = dbutils
        self.scope = scope
        self._bucket = dbutils.secrets.get(scope, "s3-bucket")
        self._session = boto3.Session(
            aws_access_key_id=dbutils.secrets.get(scope, "aws-access-key-id"),
            aws_secret_access_key=dbutils.secrets.get(scope, "aws-secret-access-key"),
            region_name=dbutils.secrets.get(scope, "aws-region"),
        )
        self._s3 = self._session.client("s3")

    @property
    def bucket(self) -> str:
        return self._bucket

    def download(self, s3_key: str, local_path: str) -> str:
        """Download arquivo do S3 para path local."""
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self._s3.download_file(self._bucket, s3_key, local_path)
        return local_path

    def upload(self, local_path: str, s3_key: str) -> str:
        """Upload arquivo local para S3."""
        self._s3.upload_file(local_path, self._bucket, s3_key)
        return f"s3://{self._bucket}/{s3_key}"

    def upload_dir(self, local_dir: str, s3_prefix: str) -> int:
        """Upload diretorio inteiro para S3. Retorna numero de arquivos."""
        count = 0
        for root, _, files in os.walk(local_dir):
            for f in files:
                local_file = os.path.join(root, f)
                rel_path = os.path.relpath(local_file, local_dir)
                s3_key = f"{s3_prefix.rstrip('/')}/{rel_path}".replace("\\", "/")
                self._s3.upload_file(local_file, self._bucket, s3_key)
                count += 1
        return count

    def download_dir(self, s3_prefix: str, local_dir: str) -> int:
        """Download todos os arquivos de um prefix S3. Retorna numero de arquivos."""
        os.makedirs(local_dir, exist_ok=True)
        paginator = self._s3.get_paginator("list_objects_v2")
        count = 0
        for page in paginator.paginate(Bucket=self._bucket, Prefix=s3_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel_path = key[len(s3_prefix):].lstrip("/")
                if not rel_path:
                    continue
                local_file = os.path.join(local_dir, rel_path)
                os.makedirs(os.path.dirname(local_file), exist_ok=True)
                self._s3.download_file(self._bucket, key, local_file)
                count += 1
        return count

    def list_keys(self, prefix: str) -> list[str]:
        """Lista chaves no S3 com dado prefix."""
        paginator = self._s3.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    def get_metadata(self, prefix: str) -> list[dict]:
        """Retorna metadata (key, size, last_modified) dos objetos."""
        paginator = self._s3.get_paginator("list_objects_v2")
        items = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                items.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                })
        return items

    def make_temp_dir(self, prefix: str = "pipeline_") -> str:
        """Cria diretorio temporario em Volumes (acessivel pelo Spark serverless).

        Serverless compute nao tem acesso ao /tmp local nem ao DBFS.
        Volumes sao o unico filesystem acessivel por boto3 E por Spark.
        """
        import uuid

        vol_base = "/Volumes/medallion/pipeline/tmp"
        tmp_path = f"{vol_base}/{prefix}{uuid.uuid4().hex[:8]}"
        os.makedirs(tmp_path, exist_ok=True)
        return tmp_path
