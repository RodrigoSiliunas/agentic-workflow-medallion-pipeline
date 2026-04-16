"""Client S3 para notebooks Databricks (serverless + cluster).

Usa dbutils.secrets para credenciais AWS (multi-tenant ready).
Cada tenant tem seu próprio secret scope com aws-access-key-id,
aws-secret-access-key, aws-region e s3-bucket.

**Leitura:** Spark nativo via `s3a://` (leitura distribuída, zero
materialização no driver). Fallback in-memory apenas quando spark
não está disponível (testes unitários locais).

**Escrita:** Spark DF → partições pandas (sem OOM) → BytesIO → S3.

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
    """Client S3 com leitura Spark nativa e escrita particionada."""

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
        # Credenciais guardadas para reuso em configure_spark_s3
        self._aws_access_key = dbutils.secrets.get(scope, "aws-access-key-id")
        self._aws_secret_key = dbutils.secrets.get(scope, "aws-secret-access-key")
        self._aws_region = dbutils.secrets.get(scope, "aws-region")
        self._session = boto3.Session(
            aws_access_key_id=self._aws_access_key,
            aws_secret_access_key=self._aws_secret_key,
            region_name=self._aws_region,
        )
        self._s3 = self._session.client("s3")
        # Flag para idempotencia do configure_spark_s3
        self._spark_configured = False

    @property
    def bucket(self) -> str:
        return self._bucket

    # ================================================================
    # Leitura: S3 → Spark DataFrame
    # ================================================================

    def configure_spark_s3(self) -> None:
        """Configura credenciais S3 no SparkSession para leitura nativa via s3a://.

        Idempotente: aplica `spark.conf.set` uma unica vez por instancia.
        Permite `spark.read.parquet("s3a://bucket/prefix")` sem precisar
        materializar arquivos no driver via boto3.

        As credenciais vem do mesmo secret scope usado pelo boto3, preservando
        o padrao multi-tenant do S3Lake.
        """
        if self._spark_configured or self.spark is None:
            return
        conf = self.spark.conf
        conf.set("spark.hadoop.fs.s3a.access.key", self._aws_access_key)
        conf.set("spark.hadoop.fs.s3a.secret.key", self._aws_secret_key)
        conf.set(
            "spark.hadoop.fs.s3a.endpoint",
            f"s3.{self._aws_region}.amazonaws.com",
        )
        self._spark_configured = True

    def read_parquet(self, s3_prefix: str):
        """Le todos os .parquet de um prefix S3 e retorna Spark DataFrame.

        Usa leitura Spark nativa via `s3a://` quando spark esta disponivel
        (leitura distribuida, zero materializacao no driver). Fallback para
        fluxo in-memory via boto3 + pandas apenas em ambientes sem Spark
        (ex: testes unitarios locais).
        """
        if self.spark is not None:
            return self.read_parquet_native(s3_prefix)
        return self._read_parquet_in_memory(s3_prefix)

    def read_parquet_native(self, s3_prefix: str):
        """Leitura Spark distribuida via s3a://, sem materializar no driver.

        Spark gerencia os particionamentos dos arquivos parquet e distribui
        a leitura entre os executors. Ideal para datasets grandes — nao ha
        risco de OOM no driver independente do tamanho do input.
        """
        if self.spark is None:
            raise RuntimeError(
                "read_parquet_native requer SparkSession (self.spark is None)"
            )
        self.configure_spark_s3()
        prefix = s3_prefix.rstrip("/")
        s3_path = f"s3a://{self._bucket}/{prefix}" if prefix else f"s3a://{self._bucket}"
        return self.spark.read.parquet(s3_path)

    def _read_parquet_in_memory(self, s3_prefix: str):
        """Fallback in-memory para ambientes sem Spark (testes unitarios).

        Fluxo: S3 → BytesIO → pandas. Materializa tudo no processo atual,
        entao nao deve ser usado com datasets grandes em producao.
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

        return pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]

    # ================================================================
    # Escrita: Spark DataFrame → S3 (particionado, sem OOM)
    # ================================================================

    def write_parquet(
        self,
        df,
        s3_prefix: str,
        filename: str = "data.parquet",
        partition_size: int = WRITE_PARTITION_SIZE,  # noqa: ARG002 — compat
    ) -> str:
        """Escreve Spark DF como parquet no S3 via writer nativo do Spark.

        T5 (PERF-02): era `count()` + `repartition()` + `randomSplit()` +
        N `toPandas()` — 3 shuffles + materialização no driver. Agora
        escrita distribuída direto pelos executors via `s3a://`.

        Produz um diretório com `part-XXXXX-*.parquet`. `filename` não
        controla mais o nome; o Spark gerencia. Se o chamador precisa
        de UM arquivo parquet unico, use `toPandas()` + `_upload_pandas`
        explicitamente (pequenos datasets apenas).

        Args:
            df: Spark DataFrame para exportar.
            s3_prefix: Prefixo S3 (ex: "silver/clean/"). Vira o path
                do diretório onde o Spark escreve os part files.
            filename: Mantido por retrocompatibilidade — ignorado pelo
                writer Spark nativo.
            partition_size: Mantido por compat — ignorado (Spark usa
                o número de partições atual do DataFrame).

        Returns:
            URL `s3a://...` do diretório onde o parquet foi escrito.
        """
        # Assegura credenciais no SparkContext pra o writer s3a funcionar.
        self.configure_spark_s3()

        s3_path = f"s3a://{self._bucket}/{s3_prefix.rstrip('/')}"
        df.write.mode("overwrite").parquet(s3_path)
        logger.info(f"write_parquet (spark native) → {s3_path}")
        return s3_path

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
