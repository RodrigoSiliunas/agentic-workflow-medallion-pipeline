"""S3 Data Lake client para notebooks Databricks (serverless-compatible).

Usa dbutils.secrets para credenciais AWS (multi-tenant ready).
Cada tenant tem seu proprio secret scope com aws-access-key-id,
aws-secret-access-key, aws-region e s3-bucket.

Abordagem in-memory: boto3 faz download/upload via BytesIO,
evitando acesso ao filesystem local (bloqueado no serverless).

Uso no notebook:
    from pipeline_lib.storage import S3Lake
    lake = S3Lake(dbutils, spark)
    df = lake.read_parquet("bronze/")           # S3 -> Spark DF
    lake.write_parquet(df, "silver/clean/")      # Spark DF -> S3
"""

import io

import boto3
import pandas as pd


class S3Lake:
    """Client S3 in-memory usando credenciais do Databricks Secrets."""

    def __init__(self, dbutils, spark=None, scope: str = "medallion-pipeline"):
        self.dbutils = dbutils
        self.spark = spark
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

    # ================================================================
    # Leitura: S3 -> Spark DataFrame (via memoria)
    # ================================================================

    def read_parquet(self, s3_prefix: str):
        """Le todos os .parquet de um prefix S3 e retorna Spark DataFrame.

        Fluxo: S3 -> BytesIO -> pandas -> Spark DataFrame
        """
        keys = self.list_keys(s3_prefix)
        parquet_keys = [k for k in keys if k.endswith(".parquet")]

        if not parquet_keys:
            raise FileNotFoundError(
                f"Nenhum .parquet em s3://{self._bucket}/{s3_prefix}"
            )

        dfs = []
        for key in parquet_keys:
            buf = io.BytesIO()
            self._s3.download_fileobj(self._bucket, key, buf)
            buf.seek(0)
            dfs.append(pd.read_parquet(buf))

        pdf = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        return self.spark.createDataFrame(pdf)

    # ================================================================
    # Escrita: Spark DataFrame -> S3 (via memoria)
    # ================================================================

    def write_parquet(self, df, s3_prefix: str, filename: str = "data.parquet"):
        """Converte Spark DF para parquet e faz upload para S3.

        Fluxo: Spark DataFrame -> pandas -> BytesIO -> S3
        """
        pdf = df.toPandas()
        buf = io.BytesIO()
        pdf.to_parquet(buf, index=False)
        buf.seek(0)

        s3_key = f"{s3_prefix.rstrip('/')}/{filename}"
        self._s3.upload_fileobj(buf, self._bucket, s3_key)
        return f"s3://{self._bucket}/{s3_key}"

    # ================================================================
    # Utilitarios S3
    # ================================================================

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

    def upload_bytes(self, data: bytes, s3_key: str) -> str:
        """Upload bytes direto para S3."""
        self._s3.upload_fileobj(io.BytesIO(data), self._bucket, s3_key)
        return f"s3://{self._bucket}/{s3_key}"
