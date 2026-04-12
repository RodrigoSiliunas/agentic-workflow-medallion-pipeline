"""Testes unitarios para S3Lake — foco no fluxo de leitura Spark nativa."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ================================================================
# Fakes para isolar dbutils, boto3 e spark
# ================================================================


class FakeSecrets:
    def __init__(self, values: dict[str, dict[str, str]]):
        self._values = values

    def get(self, scope: str, key: str) -> str:
        return self._values[scope][key]


class FakeDbutils:
    def __init__(self, secrets: FakeSecrets):
        self.secrets = secrets


class FakeSparkConf:
    def __init__(self):
        self.settings: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self.settings[key] = value


class FakeSparkReader:
    def __init__(self, parent: FakeSpark):
        self._parent = parent

    def parquet(self, path: str) -> str:
        """Retorna uma string para o teste inspecionar qual path foi lido."""
        self._parent.read_calls.append(path)
        return f"SparkDataFrame(from={path})"


class FakeSpark:
    def __init__(self):
        self.conf = FakeSparkConf()
        self.read_calls: list[str] = []
        self.read = FakeSparkReader(self)


SECRETS = {
    "medallion-pipeline": {
        "s3-bucket": "my-bucket",
        "aws-access-key-id": "AKIAFAKE",
        "aws-secret-access-key": "sekret/value",
        "aws-region": "us-east-2",
    }
}


def _make_lake(spark=None):
    """Factory helper que mocka boto3.Session e instancia S3Lake."""
    from pipeline_lib.storage.s3_client import S3Lake

    dbutils = FakeDbutils(FakeSecrets(SECRETS))
    with patch("pipeline_lib.storage.s3_client.boto3.Session") as fake_session:
        fake_session.return_value.client.return_value = object()
        return S3Lake(dbutils=dbutils, spark=spark, scope="medallion-pipeline")


# ================================================================
# configure_spark_s3
# ================================================================


class TestConfigureSparkS3:
    def test_sets_access_and_secret_keys_on_spark_conf(self):
        spark = FakeSpark()
        lake = _make_lake(spark=spark)

        lake.configure_spark_s3()

        assert spark.conf.settings["spark.hadoop.fs.s3a.access.key"] == "AKIAFAKE"
        assert spark.conf.settings["spark.hadoop.fs.s3a.secret.key"] == "sekret/value"

    def test_sets_region_endpoint(self):
        spark = FakeSpark()
        lake = _make_lake(spark=spark)

        lake.configure_spark_s3()

        assert (
            spark.conf.settings["spark.hadoop.fs.s3a.endpoint"]
            == "s3.us-east-2.amazonaws.com"
        )

    def test_is_idempotent(self):
        """Chamadas repetidas so aplicam spark.conf.set uma vez."""
        spark = FakeSpark()
        lake = _make_lake(spark=spark)

        lake.configure_spark_s3()
        lake.configure_spark_s3()
        lake.configure_spark_s3()

        # Apenas 3 chaves configuradas (access, secret, endpoint)
        assert len(spark.conf.settings) == 3

    def test_noop_when_spark_is_none(self):
        lake = _make_lake(spark=None)

        # Nao deve levantar exception — apenas nao configura nada
        lake.configure_spark_s3()

        assert lake._spark_configured is False


# ================================================================
# read_parquet_native
# ================================================================


class TestReadParquetNative:
    def test_reads_from_s3a_path(self):
        spark = FakeSpark()
        lake = _make_lake(spark=spark)

        result = lake.read_parquet_native("bronze/")

        assert result == "SparkDataFrame(from=s3a://my-bucket/bronze)"
        assert spark.read_calls == ["s3a://my-bucket/bronze"]

    def test_strips_trailing_slash(self):
        spark = FakeSpark()
        lake = _make_lake(spark=spark)

        lake.read_parquet_native("bronze//")

        assert spark.read_calls == ["s3a://my-bucket/bronze"]

    def test_handles_nested_prefix(self):
        spark = FakeSpark()
        lake = _make_lake(spark=spark)

        lake.read_parquet_native("silver/clean/")

        assert spark.read_calls == ["s3a://my-bucket/silver/clean"]

    def test_empty_prefix_reads_bucket_root(self):
        spark = FakeSpark()
        lake = _make_lake(spark=spark)

        lake.read_parquet_native("")

        assert spark.read_calls == ["s3a://my-bucket"]

    def test_configures_spark_s3_before_reading(self):
        spark = FakeSpark()
        lake = _make_lake(spark=spark)

        assert lake._spark_configured is False
        lake.read_parquet_native("bronze/")
        assert lake._spark_configured is True

    def test_raises_when_spark_missing(self):
        lake = _make_lake(spark=None)

        with pytest.raises(RuntimeError, match="requer SparkSession"):
            lake.read_parquet_native("bronze/")


# ================================================================
# read_parquet (delegation)
# ================================================================


class TestReadParquetDelegation:
    def test_delegates_to_native_when_spark_available(self):
        spark = FakeSpark()
        lake = _make_lake(spark=spark)

        result = lake.read_parquet("bronze/")

        assert result == "SparkDataFrame(from=s3a://my-bucket/bronze)"
        assert spark.read_calls == ["s3a://my-bucket/bronze"]

    def test_falls_back_to_in_memory_when_spark_missing(self):
        """Sem spark, deve usar _read_parquet_in_memory (fluxo antigo)."""
        lake = _make_lake(spark=None)

        with patch.object(lake, "_read_parquet_in_memory") as fake:
            fake.return_value = "pandas_df"
            result = lake.read_parquet("bronze/")

        fake.assert_called_once_with("bronze/")
        assert result == "pandas_df"
