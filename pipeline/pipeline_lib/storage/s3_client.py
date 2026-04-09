"""Client S3 para notebooks Databricks (serverless + cluster).

Usa dbutils.secrets para credenciais AWS (multi-tenant ready).
Cada tenant tem seu próprio secret scope com aws-access-key-id,
aws-secret-access-key, aws-region e s3-bucket.

Leitura: S3 → BytesIO → pandas → Spark DataFrame.
Escrita: Spark DF → partições pandas (sem OOM) → BytesIO → S3.

Uso:
    from pipeline_lib.storage import S3Lake

    lake = S3Lake(dbutils, spark, scope="medallion-pipeline")
    df = lake.read_parquet("bronze/")
    lake.write_parquet(df, "silver/clean/")
"""

from __future__ import annotations

import io
import logging

import boto3
import pandas as pd

logger = logging.getLogger(__name__)

# Limite de linhas por partição no write (evita OOM no driver)
WRITE_PARTITION_SIZE = 50_000


class S3Lake:
    """Client S3 in-memory com credenciais do Databricks Secrets."""

    def __init__(
        self,
        dbutils,
        spark=None,
        scope: str = "medallion-pipeline",
    ):
        self.dbutils = dbutils
        self.spark = spark
        self.scope = scope
        self._bucket = dbutils.secrets.get(scope, "s3-bucket")
        self._session = boto3.Session(
            aws_access_key_id=dbutils.secrets.get(scope, "aws-access-key-id"),
            aws_secret_access_key=dbutils.secrets.get(
                scope, "aws-secret-access-key"
            ),
            region_name=dbutils.secrets.get(scope, "aws-region"),
        )
        self._s3 = self._session.client("s3")

    @property
    def bucket(self) -> str:
        return self._bucket

    # ================================================================
    # Leitura: S3 → Spark DataFrame
    # ================================================================

    def read_parquet(self, s3_prefix: str):
        """Lê todos os .parquet de um prefix S3 e retorna Spark DataFrame.

        Fluxo: S3 → BytesIO → pandas → Spark DataFrame.
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
    # Escrita: Spark DataFrame → S3 (particionado, sem OOM)
    # ================================================================

    def write_parquet(
        self,
        df,
        s3_prefix: str,
        filename: str = "data.parquet",
        partition_size: int = WRITE_PARTITION_SIZE,
    ) -> str:
        """Converte Spark DF para parquet e faz upload para S3.

        Usa toPandas() em partições para evitar OOM no driver.
        Cada partição é convertida separadamente e enviada ao S3.

        Args:
            df: Spark DataFrame para exportar.
            s3_prefix: Prefixo S3 (ex: "silver/clean/").
            filename: Nome do arquivo parquet.
            partition_size: Máximo de linhas por partição (default 50k).

        Returns:
            URL S3 do arquivo (ou último arquivo se particionado).
        """
        total_rows = df.count()

        if total_rows <= partition_size:
            # Dataset pequeno — conversão direta (mais rápido)
            pdf = df.toPandas()
            return self._upload_pandas(pdf, s3_prefix, filename)

        # Dataset grande — particiona para evitar OOM
        logger.info(
            f"Write particionado: {total_rows} rows em "
            f"chunks de {partition_size}"
        )
        num_partitions = (total_rows // partition_size) + 1
        df_repartitioned = df.repartition(num_partitions)
        partitions = df_repartitioned.randomSplit(
            [1.0] * num_partitions
        )

        last_url = ""
        for i, partition_df in enumerate(partitions):
            pdf = partition_df.toPandas()
            if pdf.empty:
                continue
            part_name = (
                f"part-{i:05d}-{filename}"
                if len(partitions) > 1
                else filename
            )
            last_url = self._upload_pandas(pdf, s3_prefix, part_name)
            logger.info(f"  Partição {i}: {len(pdf)} rows → {part_name}")

        return last_url

    def _upload_pandas(
        self, pdf: pd.DataFrame, s3_prefix: str, filename: str
    ) -> str:
        """Upload de um pandas DataFrame como parquet para S3."""
        buf = io.BytesIO()
        pdf.to_parquet(buf, index=False)
        buf.seek(0)

        s3_key = f"{s3_prefix.rstrip('/')}/{filename}"
        self._s3.upload_fileobj(buf, self._bucket, s3_key)
        return f"s3://{self._bucket}/{s3_key}"

    # ================================================================
    # Utilitários S3
    # ================================================================

    def _paginate_objects(self, prefix: str):
        """Itera sobre todos os objetos S3 com dado prefix."""
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self._bucket, Prefix=prefix
        ):
            yield from page.get("Contents", [])

    def list_keys(self, prefix: str) -> list[str]:
        """Lista chaves no S3 com dado prefix."""
        return [obj["Key"] for obj in self._paginate_objects(prefix)]

    def get_metadata(self, prefix: str) -> list[dict]:
        """Retorna metadata (key, size, last_modified) dos objetos."""
        return [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            }
            for obj in self._paginate_objects(prefix)
        ]

    def upload_bytes(self, data: bytes, s3_key: str) -> str:
        """Upload bytes direto para S3."""
        self._s3.upload_fileobj(io.BytesIO(data), self._bucket, s3_key)
        return f"s3://{self._bucket}/{s3_key}"
