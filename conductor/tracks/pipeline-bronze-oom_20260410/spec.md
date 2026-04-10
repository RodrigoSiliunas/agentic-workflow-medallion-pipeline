# Specification: Pipeline — Fix OOM em bronze_ingestion

**Track ID:** pipeline-bronze-oom_20260410
**Type:** Bug
**Created:** 2026-04-10
**Status:** Draft
**Priority:** Alta — bloqueia o pipeline end-to-end

## Summary

O `bronze_ingestion` falha com `java.lang.OutOfMemoryError: GC overhead limit exceeded` no cluster `m5d.large` (2 cores, 8 GB RAM) ao tentar ler ~153k mensagens parquet do S3. O notebook roda retries (3x) mas todas estouram o heap.

## Evidencia

Run `1063328173422554` (pipeline normal pos-refactor observer-framework):
- `pre_check` → SUCCESS (path novo funcionou)
- `bronze_ingestion` attempt 0 → FAILED com:
  ```
  Py4JJavaError: An error occurred while calling o585.getResult.
  : org.apache.spark.SparkException: Exception thrown in awaitResult:
  Job aborted due to stage failure: Task 0 in stage 92.0 failed 1 times,
  most recent failure: Lost task 0.0 in stage 92.0 (TID 1970)
  (ip-10-153-234-39.compute.internal executor driver):
  java.lang.OutOfMemoryError: GC overhead limit exceeded
  ```
- attempts 1, 2 → mesmo erro
- Pipeline cancelado manualmente apos multiplas retries

## Context

A classe `S3Lake.read_parquet()` em `pipelines/pipeline-seguradora-whatsapp/pipeline_lib/storage/s3_client.py` usa uma estrategia **in-memory via driver**:

1. Para cada chave parquet no prefixo S3, baixa via `boto3` para `BytesIO`
2. Carrega em pandas via `pd.read_parquet(buf)`
3. `pd.concat(dfs, ignore_index=True)` junta tudo no driver
4. `spark.createDataFrame(pdf)` converte para Spark DataFrame

Para 153k linhas com ~14 colunas, o `pd.concat` + `createDataFrame` consome multiplos GB de heap (estruturas duplicadas durante conversao). O cluster `m5d.large` tem apenas 8 GB de RAM total, dos quais o driver recebe uma fracao menor apos overhead do JVM, Python worker e cache de Delta/Spark.

**Por que funcionou antes:** runs anteriores tiveram sorte com cluster quente (caches mais enxutos, GC com mais folga) ou processaram menos dados simultaneos. Eh uma bomba-relogio.

**Por que nao eh problema do refactor:** o codigo do `s3_client.py` nao mudou na reestruturacao — apenas foi movido de path. O refactor apenas exposuo o problema porque forcou um run limpo em cluster "normal".

## User Story

Como engenheiro de dados, quero que o pipeline `medallion_pipeline_whatsapp` rode end-to-end no cluster atual sem OOM, para poder validar o fluxo completo do Observer Agent (bronze -> silver -> gold -> validation -> observer em caso de falha).

## Acceptance Criteria

- [ ] `bronze_ingestion` executa em menos de 10 minutos sem OOM, processando os 153k mensagens do S3
- [ ] Pipeline completo (pre_check + bronze + silver x3 + gold + validation) roda end-to-end com SUCCESS
- [ ] `observer_trigger` fica como EXCLUDED (nenhuma task falha) em execucao normal
- [ ] Testes unitarios de `S3Lake` continuam passando com mocks atualizados
- [ ] Cluster permanece `m5d.large` — fix deve ser eficiente, nao apenas "aumentar RAM"
- [ ] Chaos test `bronze_schema` continua funcionando (o Observer dispara como antes)

## Dependencies

Nenhuma. A track pode ser executada assim que aprovada.

## Out of Scope

- Redesign completo do `S3Lake` — o escopo eh apenas o `read_parquet`. O `write_parquet` ja usa particionamento em chunks de 50k linhas e nao tem o problema.
- Upgrade de cluster — m5d.large eh o cluster atual pago pelo trial Databricks; fix deve ser eficiente na memoria atual.
- Migrar pipeline inteiro para external tables — escopo e prazo nao permitem.

## Technical Notes

### Tres opcoes avaliadas

#### Opcao A: Spark nativo via DBFS credentials passthrough (preferida)

O Databricks pode ser configurado para fazer credential passthrough automatico: o cluster usa uma **IAM Instance Profile** anexada ao EC2, e o Spark consegue ler `s3://bucket/key` nativamente sem precisar de credenciais em codigo.

```python
# Ao inves de:
df = lake.read_parquet("bronze/")

# Simplesmente:
df = spark.read.parquet(f"s3://{bucket}/bronze/")
```

**Vantagens:**
- Zero materializacao no driver — Spark lê distribuido pelos executors
- Zero OOM porque usa o mecanismo nativo de particionamento do Spark
- Codigo mais simples (3 linhas vs 30)

**Desvantagens:**
- Requer IAM Instance Profile configurada no cluster (nao sei se ja existe)
- Perde o "multi-tenant via Databricks Secrets" — se diferentes pipelines quiserem acessar buckets de clientes diferentes, precisamos de `External Locations` no Unity Catalog

**Viabilidade:** depende de verificar o setup atual do cluster. Se houver Instance Profile, eh a opcao mais limpa.

#### Opcao B: `spark.read.parquet` com credenciais via `spark.hadoop.*`

Configurar as credenciais AWS no contexto Spark antes do read:

```python
spark.conf.set("spark.hadoop.fs.s3a.access.key", dbutils.secrets.get(SCOPE, "aws-access-key-id"))
spark.conf.set("spark.hadoop.fs.s3a.secret.key", dbutils.secrets.get(SCOPE, "aws-secret-access-key"))
df = spark.read.parquet(f"s3a://{bucket}/bronze/")
```

**Vantagens:**
- Mantem o padrao "credenciais via Databricks Secrets" (multi-tenant via scope)
- Spark le distribuido, zero OOM
- Nao depende de IAM Instance Profile

**Desvantagens:**
- `spark.conf.set` afeta toda a sessao — mudanca global
- `s3a://` precisa do driver `hadoop-aws` instalado (vem no DBR por padrao)

**Viabilidade:** alta. Funciona em qualquer cluster com DBR + boto3.

#### Opcao C: Mount S3 via `dbutils.fs.mount`

Montar o bucket S3 via `dbutils.fs.mount` e ler via `/mnt/<name>/bronze/`.

**Vantagens:**
- Padroniza acesso S3 como se fosse filesystem

**Desvantagens:**
- `dbutils.fs.mount` eh deprecado em favor de External Locations / Volumes
- Mount eh por workspace, nao por pipeline — nao escala para multi-tenant
- Complexidade operacional extra (criar/deletar mounts)

**Viabilidade:** baixa. Nao recomendado.

### Decisao recomendada

**Opcao B** — `spark.read.parquet` via `s3a://` com credenciais configuradas em `spark.conf`. Razoes:

1. Preserva o padrao multi-tenant via Databricks Secrets (cada scope traz credenciais do seu tenant)
2. Nao depende de configuracao de cluster (funciona em qualquer DBR atual)
3. Zero OOM porque Spark le distribuido
4. Migracao minima — `S3Lake` ganha uma variante `read_parquet_native` que usa Spark, e `read_parquet` existente vira fallback para casos em que `spark` nao esta disponivel

### Teste de aceitacao

1. Validar sem OOM: pipeline normal completa bronze_ingestion em menos de 5 minutos
2. Validar dados corretos: `SELECT COUNT(*) FROM medallion.bronze.conversations` retorna ~153k (mesmo valor que runs anteriores)
3. Validar que chaos_mode continua funcionando: chaos test `bronze_schema` dispara o Observer como antes

---

_Generated by Conductor._
