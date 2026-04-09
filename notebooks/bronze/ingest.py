# Não é possível fornecer código corrigido completo sem acesso ao notebook original notebooks/bronze/ingest.py
# Segue exemplo de como implementar validação de schema defensiva:

from pyspark.sql import DataFrame
from pyspark.sql.functions import col
from delta.tables import DeltaTable

def validate_and_clean_schema(df: DataFrame, expected_columns: list) -> DataFrame:
    """
    Remove colunas que não fazem parte do schema esperado
    """
    # Filtrar apenas colunas válidas
    valid_columns = [c for c in df.columns if c in expected_columns]
    
    # Log colunas removidas para auditoria
    invalid_columns = [c for c in df.columns if c not in expected_columns]
    if invalid_columns:
        print(f"AVISO: Removendo colunas inválidas: {invalid_columns}")
    
    return df.select(*valid_columns)

# Schema esperado para conversations (precisa ser definido baseado no contrato)
EXPECTED_BRONZE_CONVERSATIONS_SCHEMA = [
    # Definir colunas baseado no contrato real
    # Exemplo: 'id', 'timestamp', 'user_id', 'message', 'channel', etc.
]

# No código de ingestão:
# df_raw = spark.read... (leitura da fonte)
# df_clean = validate_and_clean_schema(df_raw, EXPECTED_BRONZE_CONVERSATIONS_SCHEMA)
# df_clean.write.format('delta').mode('append').saveAsTable('medallion.bronze.conversations')