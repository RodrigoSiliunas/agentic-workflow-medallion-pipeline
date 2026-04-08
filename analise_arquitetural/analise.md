# Analise Arquitetural -- Pipeline Agentico de Dados Medallion

## Sumario

1. [Visao Geral da Arquitetura](#1-visao-geral-da-arquitetura)
2. [Estrutura de Diretorios Proposta](#2-estrutura-de-diretorios-proposta)
3. [Design do Pipeline por Camada](#3-design-do-pipeline-por-camada)
4. [Design do Agente Autonomo](#4-design-do-agente-autonomo)
5. [Stack Tecnologica Recomendada](#5-stack-tecnologica-recomendada)
6. [Estrategia de Dados Sensiveis](#6-estrategia-de-dados-sensiveis)
7. [Diferenciais Competitivos](#7-diferenciais-competitivos)
8. [Plano de Implementacao](#8-plano-de-implementacao)
9. [Riscos e Mitigacoes](#9-riscos-e-mitigacoes)

### 1.1 Diagrama de Alto Nivel

```
+-----------------------------------------------------------------------+
|                           AWS ACCOUNT                                  |
|                                                                        |
|   +------------------+        +--------------------------------------+ |
|   |     S3 (Data     |        |       DATABRICKS WORKSPACE            | |
|   |      Lake)       |        |                                       | |
|   |                  |        | Workflow: medallion_pipeline            | |
|   | /bronze/         |        | Trigger: cron diario (1x/dia)         | |
|   |  conversations   |        |                                       | |
|   |  _bronze.parquet |------->|  Task 0: AGENTE PRE-CHECK             | |
|   |  (dados chegam   |        |    |  Verifica novos dados, versoes   | |
|   |   externamente)  |        |    |  Delta, seta task values         | |
|   |                  |        |    +-> Task 1: Bronze Ingestion       | |
|   | /silver/         |<-------+    |    Parquet cru -> Delta Table      | |
|   |  messages_clean/ |        |    +-> Task 2a: Silver Dedup+Clean   | |
|   |  leads_profile/  |        |    +-> Task 2b: Entities+Mask        | |
|   |  conversations/  |        |    +-> Task 2c: Enrichment           | |
|   |                  |        |    +-> Task 3: Gold Analytics         | |
|   | /gold/           |<-------+    |    12 tabelas analiticas          | |
|   |  funil_vendas/   |        |    +-> Task 4: Quality Validation     | |
|   |  agent_perf/     |        |    +-> Task 5: AGENTE POST-CHECK     | |
|   |  sentiment/      |        |         recovery, email, estado        | |
|   |  lead_scoring/   |        |                                       | |
|   +------------------+        |                                       | |
|                               | Unity Catalog                          | |
|                               |   bronze.conversations                 | |
|                               |   silver.messages_clean                | |
|                               |   silver.leads_profile                 | |
|                               |   gold.*                               | |
|                               +--------------------------------------+ |
+-----------------------------------------------------------------------+

Fluxo de producao:
  1. Dados chegam no S3 /bronze/ (via sistema externo, Parquet cru)
  2. Workflow dispara 1x/dia (cron), max_concurrent_runs=1
  3. Agent Pre (Task 0) verifica se ha dados novos, registra versoes Delta
  4. Se sim: Bronze -> Silver (2a/2b/2c) -> Gold -> Validation
  5. Agent Post (Task 5) SEMPRE roda: verifica resultados, recovery, email
  6. Se sucesso: email resumo. Se falha corrigida: email correcao. Se falha: email critico.
```

### 1.2 Diagrama de Fluxo de Dados (Mermaid)

```mermaid
graph TD
    EXT[Sistema Externo] -->|deposita dados| S3[S3 /bronze/]
    CRON[Cron Diario] -->|dispara| WF

    subgraph Databricks Workflow - max_concurrent_runs=1
        WF[Trigger] --> PRE[Task 0: Agent Pre-Check]
        PRE -->|verifica novos dados| S3
        PRE -->|ha dados novos| B[Task 1: Bronze Ingestion]
        PRE -->|sem dados novos| POST

        B -->|Landing -> Delta Table| BC[bronze.conversations]
        BC --> S2A[Task 2a: Silver Dedup+Clean]
        S2A --> S2B[Task 2b: Silver Entities+Mask]
        S2A --> S2C[Task 2c: Silver Enrichment]
        S2B --> H[Task 3: Gold Analytics]
        S2C --> H
        H --> N[Task 4: Quality Validation]

        N --> POST[Task 5: Agent Post-Check]
        POST -->|sucesso| EMAIL_OK[Email: resumo]
        POST -->|correcao OK| EMAIL_REC[Email: correcao realizada]
        POST -->|falha| EMAIL_FAIL[Email: CRITICO]
    end
```

### 1.3 Fluxo de Producao

O pipeline e **100% cloud** — nada roda localmente em producao. O ambiente local existe apenas para desenvolvimento.

**Fluxo diario**:
1. Dados brutos chegam no S3 `/bronze/` via sistema externo (CRM, plataforma de WhatsApp, etc.)
2. Databricks Workflow dispara **1x/dia** via cron
3. **Agente (Task 0)** inicializa e verifica se ha dados novos no S3 desde a ultima execucao
4. Se ha dados novos: executa Bronze → Silver → Gold → Validation
5. Se uma task falha: agente decide — retry, rollback, ou alerta
6. Se nao ha dados novos: workflow encerra sem processar (idempotente)

**Componentes**:

| Componente | Papel |
|------------|-------|
| **AWS S3** | Data lake. `/bronze/` (Parquet cru), `/silver/` e `/gold/` (Delta Tables). Dados chegam externamente no `/bronze/`. |
| **Databricks Workflow** | Cron diario que dispara o DAG completo. Gerencia retries e alertas nativos. |
| **Agente (Task 0)** | Notebook Python que orquestra: verifica novos dados, dispara tasks, monitora, faz recovery. |
| **Unity Catalog** | Governanca: schema registry, linhagem Bronze→Silver→Gold, controle de acesso. |
| **Delta Lake** | Formato de storage. ACID, schema evolution (`mergeSchema`), time travel, audit. |

### 1.4 Principios Arquiteturais

| Principio | Aplicacao |
|-----------|-----------|
| **Separacao de Responsabilidades** | Cada camada tem transformacoes isoladas; o agente nao conhece logica de negocio |
| **Idempotencia** | Qualquer etapa pode ser re-executada sem efeitos colaterais duplicados |
| **Imutabilidade de Dados** | Bronze nunca e alterado; Silver e Gold sao regeneraveis a partir de Bronze |
| **Schema Evolution** | Colunas novas sao aceitas e propagadas. Apenas colunas obrigatorias sao validadas. Delta Lake `mergeSchema` e o mecanismo. |
| **Fail-Safe** | Falha em uma task do Workflow nao corrompe dados (Delta ACID). Retry automatico configrado. |
| **Observabilidade** | Delta Tables de metricas + estado + notificacoes. Dashboard Databricks SQL. Alerts proativos. Emails via agent_post. |
| **Extensibilidade** | Novas tabelas Gold = novo notebook + nova task no Workflow. Sem alterar Silver. |

---

## 2. Estrutura de Diretorios Proposta

```
medallion-pipeline/
|
|-- pyproject.toml                  # Dependencias (uv/pip)
|-- README.md                       # Documentacao e instrucoes de setup
|-- .gitignore
|
|-- notebooks/                      # Notebooks Databricks (o que roda na cloud)
|   |-- agent_pre.py                # Task 0: pre-check (dados novos? versoes Delta? go/no-go)
|   |-- agent_post.py               # Task 5: post-check (resultados, recovery, email, estado)
|   |
|   |-- bronze/
|   |   |-- ingest.py               # Landing zone -> Delta Table bronze.conversations
|   |
|   |-- silver/
|   |   |-- dedup_clean.py          # Task 2a: dedup + normalizacao + metadata -> messages_clean
|   |   |-- entities_mask.py        # Task 2b: extracao + mascaramento + redaction -> leads_profile
|   |   |-- enrichment.py           # Task 2c: enriquecimento por conversa -> conversations_enriched
|   |
|   |-- gold/
|   |   |-- analytics.py            # Orquestrador Gold: gera todas as tabelas
|   |   |-- funnel.py               # Funil de conversao e vendas
|   |   |-- agent_performance.py    # Scoring e ranking de vendedores
|   |   |-- sentiment.py            # Analise de sentimento (heuristica + ML)
|   |   |-- lead_scoring.py         # Scoring de leads
|   |   |-- segmentation.py         # Personas e audiencias
|   |   |-- competitor_intel.py     # Inteligencia competitiva
|   |   |-- temporal_analysis.py    # Analise de horario otimo
|   |   |-- campaign_roi.py         # Eficacia de campanhas
|   |   |-- churn_reengagement.py   # Reengajamento de leads
|   |   |-- negotiation_complexity.py # Complexidade da negociacao
|   |   |-- first_contact_resolution.py # Resolucao no primeiro contato
|   |
|   |-- validation/
|       |-- checks.py               # Quality checks Bronze->Silver->Gold
|
|-- lib/                            # Codigo Python puro (compartilhado)
|   |-- extractors/                 # Extratores de entidades
|   |   |-- __init__.py
|   |   |-- cpf.py                  # Regex + validacao CPF
|   |   |-- email.py                # Regex email
|   |   |-- phone.py                # Regex telefone BR
|   |   |-- plate.py                # Placa Mercosul + antiga
|   |   |-- vehicle.py              # Marca/modelo/ano
|   |   |-- cep.py                  # CEP
|   |   |-- competitor.py           # Seguradoras concorrentes
|   |   |-- price.py                # Valores monetarios (R$)
|   |
|   |-- masking/                    # Mascaramento de dados sensiveis
|   |   |-- __init__.py
|   |   |-- format_preserving.py    # Mascara preservando formato
|   |   |-- hash_based.py           # Hash HMAC deterministico
|   |
|   |-- schema/                     # Validacao e evolucao de schema
|       |-- __init__.py
|       |-- validator.py            # Validacao com schema evolution
|       |-- contracts.py            # Required columns + constraints
|
|-- tests/                          # Testes (rodam localmente durante dev)
|   |-- test_extractors/
|   |-- test_masking/
|   |-- test_schema/
|   |-- fixtures/                   # Dados sinteticos para teste
|
|-- data/                           # Dados locais para dev (gitignored)
|   |-- conversations_bronze.parquet
```

### Justificativa da Estrutura

**`agent_pre.py` + `agent_post.py`** -- O agente e dividido em duas tasks do Workflow. `agent_pre` (Task 0) faz pre-check: dados novos? versoes Delta para rollback? `agent_post` (Task 5) faz pos-check: resultados, recovery, notificacoes, estado. Separar em dois garante que o agente executa logica APOS as tasks de dados.

**`notebooks/silver/`** -- Silver desacoplada em 3 tasks independentes (dedup_clean, entities_mask, enrichment). Se uma falhar, as outras preservam o trabalho ja feito. Task 2b e 2c podem rodar em paralelo (ambas dependem de 2a).

**`lib/`** -- Logica Python pura (regex, heuristica, validacao de schema). Deployado como wheel no cluster Databricks ou via Repos. Testavel localmente sem Spark.

**Sem `agent/` local**: Em producao nao existe processo local. Tudo roda no Databricks. O desenvolvimento e feito localmente e deployado via Databricks Repos (sync com GitHub) ou upload manual.

---

## 3. Design do Pipeline por Camada

### 3.1 Bronze Layer -- Ingestao e Armazenamento Bruto

#### Conceito: Landing Zone vs. Bronze Delta Table

O Parquet cru no S3 `/bronze/` e o dado de origem. O Bronze propriamente dito e uma **Delta Table** registrada no Unity Catalog, criada a partir desse Parquet. Isso permite:
- Preservar o arquivo original intocado no S3 (auditoria)
- Aplicar schema evolution no Bronze Delta sem alterar a fonte
- Usar Delta Lake features (time travel, audit log) desde a primeira camada

```
S3 /bronze/conversations_bronze.parquet    <-- arquivo cru, intocado
        |
        v  (Bronze Ingestion le e registra)
Unity Catalog: bronze.conversations        <-- Delta Table com schema evolution
```

#### Responsabilidades
- Ler Parquet cru do S3 `/bronze/`
- Validar schema com evolucao (colunas obrigatorias + aceitar novas)
- Registrar como Delta Table `bronze.conversations` no Unity Catalog
- Nenhuma transformacao — dados exatamente como recebidos, apenas formato Delta

#### Estrategia de Deteccao de Mudancas

```python
# Usar S3 metadata (ETag + LastModified) — O(1), sem ler o arquivo
def get_bronze_fingerprint(spark, s3_path: str) -> str:
    """Detecta mudancas via metadados do S3 (sem ler o conteudo)."""
    files = dbutils.fs.ls(s3_path)
    # ETag muda quando o arquivo e reescrito; LastModified quando e atualizado
    fingerprint = "|".join(
        f"{f.name}:{f.size}:{f.modificationTime}" for f in sorted(files, key=lambda x: x.name)
    )
    return hashlib.sha256(fingerprint.encode()).hexdigest()
```

Decisao: Usar **S3 metadata (ETag/LastModified/size)** em vez de hash do conteudo. E O(1) — nao precisa ler o arquivo. Se o arquivo for substituido, o LastModified e o size mudam. Se for modificado in-place, o ETag muda. Robusto e instantaneo.

#### Validacao de Schema com Evolucao

O schema deve ser **aberto para evolucao**: aceitar novas colunas (escala horizontal) e novas linhas/dados (escala vertical) sem quebrar o pipeline.

**Estrategia: Schema mínimo obrigatório + colunas livres**

```python
# Colunas obrigatorias (o pipeline depende delas para funcionar)
REQUIRED_COLUMNS = {
    "message_id", "conversation_id", "timestamp", "direction",
    "sender_phone", "sender_name", "message_type", "message_body",
    "status", "channel", "campaign_id", "agent_id",
    "conversation_outcome", "metadata"
}

# Validacoes de integridade (nos dados, nao no schema)
VALUE_CONSTRAINTS = {
    "conversation_id": r"^conv_[0-9a-f]{8}$",
    "direction": {"inbound", "outbound"},
    "message_type": {"text", "audio", "image", "document", "sticker", "contact", "video", "location"},
}

def validate_schema(df_schema: set[str]) -> tuple[bool, list[str]]:
    missing = REQUIRED_COLUMNS - df_schema
    new_cols = df_schema - REQUIRED_COLUMNS

    if missing:
        return False, [f"ERRO: colunas obrigatorias ausentes: {missing}"]

    warnings = []
    if new_cols:
        # Colunas novas sao ACEITAS e propagadas para Silver
        warnings.append(f"INFO: {len(new_cols)} colunas novas detectadas: {new_cols}")
        warnings.append("Colunas novas serao preservadas nas camadas subsequentes")
    return True, warnings
```

**Principios de evolucao do schema**:

| Cenario | Comportamento |
|---------|--------------|
| Colunas obrigatorias presentes | Pipeline executa normalmente |
| Colunas novas aparecem (ex: `lead_score_external`, `utm_source`) | Aceitar, propagar para Silver/Gold, logar como INFO |
| Coluna obrigatoria removida | BLOQUEAR + alerta. Pipeline nao pode funcionar sem ela |
| Tipos de dados mudam em coluna existente | Tentar cast automatico, alertar se falhar |
| Novos valores em campos enum (ex: novo `message_type`) | Aceitar, categorizar como "outros" nas agregacoes Gold |
| Linhas novas (escala vertical) | Processamento incremental, sem reprocessar historico |

**Colunas novas na Silver**: colunas extras do Bronze sao copiadas as-is para Silver. Se contiverem dados sensiveis, o pipeline aplica deteccao heuristica (regex de CPF/email/phone) e mascara automaticamente.

**Colunas novas na Gold**: tabelas de agregacao ignoram colunas desconhecidas (nao quebram). Se uma coluna nova for relevante para analytics, ela pode ser incorporada em tabelas Gold futuras sem alterar as existentes.

#### Particionamento

Para o volume atual (153k linhas, ~9MB), particionamento nao e necessario. Porem, para demonstrar capacidade de escalar:

```
data/bronze/
  |-- year=2026/
      |-- month=02/
          |-- conversations_bronze.parquet
```

Isso permite que o pipeline processe incrementalmente quando novos meses chegarem.

---

### 3.2 Silver Layer -- Limpeza e Estruturacao

A Silver Layer e o nucleo de engenharia de dados. Ela transforma 153.228 linhas brutas em dados estruturados e limpos. Divide-se em 3 tabelas de saida.

#### 3.2.1 Tabela: `messages_clean` -- Mensagens Deduplicadas e Limpas

**Estrategia de Deduplicacao (sent + delivered)**

O dataset contem duplicatas onde a mesma mensagem aparece com `status=sent` e `status=delivered`. A estrategia:

1. Agrupar por `(conversation_id, message_id, timestamp, direction, sender_name, message_body)`
2. Priorizar o status mais avancado: `read` > `delivered` > `sent`
3. Manter apenas uma linha por mensagem real

```python
# PySpark -- deduplicacao por prioridade de status
from pyspark.sql import functions as F, Window

status_priority = F.when(F.col("status") == "read", 3) \
                   .when(F.col("status") == "delivered", 2) \
                   .otherwise(1)

w = Window.partitionBy(
    "conversation_id", "message_id", "timestamp", "direction", "sender_name"
).orderBy(status_priority.desc())

df = (
    df.withColumn("rank", F.row_number().over(w))
    .filter(F.col("rank") == 1)
    .drop("rank")
)
```

Estimativa de impacto: Das 153k linhas, ~10.6k sao `sent` que provavelmente tem um `delivered` correspondente. Esperamos reduzir para ~142-145k linhas.

**Tratamento por `message_type`**

| Tipo | Volume | Tratamento |
|------|--------|------------|
| `text` | 146.817 | Processar normalmente |
| `audio` | 4.000 | Remover prefixo `[audio transcrito]`, flag `is_audio_transcription=true` |
| `image` | 903 | `message_body` vazio -> setar `[imagem]`, flag `has_media=true` |
| `document` | 624 | `message_body` vazio -> setar `[documento]`, flag `has_media=true` |
| `sticker` | 420 | `message_body` vazio -> setar `[sticker]`, flag `has_media=true` |
| `contact` | 233 | Tentar extrair dados do contato compartilhado |
| `video` | 231 | `message_body` vazio -> setar `[video]`, flag `has_media=true` |
| `location` | 230 | Tentar extrair coordenadas se presentes |

**Normalizacao de `sender_name`**

Problemas identificados: casing inconsistente, abreviacoes, acentos, valores vazios.

```python
def normalize_name(name: str, conversation_id: str, direction: str) -> str:
    if not name or name.strip() == "":
        # Para outbound sem nome, usar agent_id como fallback
        # Para inbound sem nome, usar "Lead_{conversation_id[-8:]}"
        return fallback_name(conversation_id, direction)

    name = name.strip()
    name = unicodedata.normalize("NFKD", name)  # Normalizar acentos
    # Preservar acentos, apenas normalizar representacao Unicode
    name = name.title()  # "JOAO SILVA" -> "Joao Silva"
    name = re.sub(r'\s+', ' ', name)  # Multiplos espacos -> 1
    return name
```

Abordagem para resolver abreviacoes do mesmo lead dentro de uma conversa: agrupar por `conversation_id` + `direction=inbound`, pegar o nome mais longo (mais completo), e usar como nome canonico para todas as mensagens inbound daquela conversa.

**Parse de `metadata` JSON**

```python
# Expandir metadata JSON em colunas tipadas
df = df.with_columns(
    F.get_json_object("metadata", "$.device").alias("device"),
    F.get_json_object("metadata", "$.city").alias("city"),
    F.get_json_object("metadata", "$.state").alias("state"),
    F.get_json_object("metadata", "$.response_time_sec")
        .cast(pl.Float64, strict=False).alias("response_time_sec"),
    F.get_json_object("metadata", "$.is_business_hours")
        .cast(pl.Boolean, strict=False).alias("is_business_hours"),
    F.get_json_object("metadata", "$.lead_source").alias("lead_source"),
)
```

#### 3.2.2 Tabela: `leads_profile` -- Perfil Estruturado por Lead

Uma linha por `conversation_id`, agregando todas as entidades extraidas das mensagens inbound.

**Estrategia de Extracao de Entidades (NER via Regex)**

Cada extrator retorna `list[str]` de matches encontrados em todo o texto inbound da conversa.

**CPF** -- `src/extractors/cpf.py`

```python
# Formatos encontrados nos dados:
# "418.696.561-30" (formatado)
# "41869656130" (apenas digitos)
# "o cpf eh 418.696.561-30"
# Audio: "o cpf eh quatro um oito seis nove seis..." (edge case)

CPF_PATTERN = re.compile(
    r'\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b'
)

def extract_cpf(text: str) -> list[str]:
    matches = CPF_PATTERN.findall(text)
    # Validar digitos verificadores para eliminar falsos positivos
    return [cpf for cpf in matches if validate_cpf_digits(cpf)]
```

**Email** -- `src/extractors/email.py`

```python
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)
```

**Telefone** -- `src/extractors/phone.py`

```python
# Formatos BR:
# (11) 99999-9999, 11999999999, +5511999999999
# "meu numero eh 11 9 8765 4321"
PHONE_PATTERN = re.compile(
    r'(?:\+?55\s?)?'           # DDI opcional
    r'(?:\(?\d{2}\)?\s?)?'     # DDD opcional
    r'(?:9\s?)?'               # Nono digito
    r'\d{4}[\s-]?\d{4}'        # Numero
)
```

**Placa de Veiculo** -- `src/extractors/plate.py`

```python
# Mercosul: ABC1D23 (3 letras, 1 digito, 1 letra, 2 digitos)
# Antiga: ABC-1234 (3 letras, 4 digitos)
PLATE_MERCOSUL = re.compile(r'\b([A-Z]{3}\d[A-Z]\d{2})\b', re.IGNORECASE)
PLATE_OLD = re.compile(r'\b([A-Z]{3}-?\d{4})\b', re.IGNORECASE)

# Exemplo real: "placa SYL8V26" -> match Mercosul
```

**Veiculo (marca/modelo/ano)** -- `src/extractors/vehicle.py`

Este e o extrator mais complexo. Dados aparecem desordenados: "gol 2019 1.0 placa ABC1D23", "Onix ano 2015 cor prata".

```python
# Estrategia: dicionario de marcas/modelos conhecidos + regex de ano
KNOWN_MODELS = {
    "onix", "gol", "hb20", "civic", "corolla", "kwid", "mobi",
    "uno", "polo", "t-cross", "creta", "tracker", "compass",
    "renegade", "kicks", "hr-v", "fit", "city", "argo", "cronos",
    "toro", "hilux", "s10", "ranger", "amarok", "saveiro",
    # ... lista completa de modelos populares no BR
}

YEAR_PATTERN = re.compile(r'\b(19[89]\d|20[012]\d)\b')
COLOR_PATTERN = re.compile(
    r'\b(prat[ao]|branc[ao]|pret[ao]|cinza|vermelho|azul|'
    r'dourad[ao]|bege|verde|marrom|vinho|champagne)\b',
    re.IGNORECASE
)

def extract_vehicle_info(text: str) -> dict:
    text_lower = text.lower()
    model = next((m for m in KNOWN_MODELS if m in text_lower), None)
    year = YEAR_PATTERN.search(text)
    color = COLOR_PATTERN.search(text)
    return {
        "vehicle_model": model,
        "vehicle_year": year.group() if year else None,
        "vehicle_color": color.group() if color else None,
    }
```

**CEP** -- `src/extractors/cep.py`

```python
CEP_PATTERN = re.compile(r'\b(\d{5}-?\d{3})\b')
```

**Concorrentes** -- `src/extractors/competitor.py`

```python
COMPETITORS = [
    "porto seguro", "portoseguro", "porto",
    "hdi", "hdi seguros",
    "suhai", "sulamerica", "sul america",
    "bradesco seguros", "bradesco",
    "liberty", "liberty seguros",
    "mapfre", "allianz", "tokio marine",
    "azul seguros", "sompo", "zurich",
]

# Detectar mencoes + extrair valor se presente
# "HDI Seguros me ofereceu por R$ 1903"
PRICE_PATTERN = re.compile(r'R\$\s?([\d.,]+)')
```

**Valores Monetarios** -- `src/extractors/price.py`

```python
PRICE_PATTERN = re.compile(
    r'R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)'
)
# "R$ 1903", "R$ 1.903,00", "R$1903"
```

**Esquema da tabela `leads_profile`:**

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| conversation_id | str | Chave primaria |
| lead_name | str | Nome normalizado do lead |
| agent_id | str | Vendedor responsavel |
| campaign_id | str | Campanha de origem |
| cpf_masked | str | CPF mascarado (###.###.###-XX) |
| email_masked | str | Email mascarado |
| phone_masked | str | Telefone mascarado |
| plate_masked | str | Placa mascarada |
| cep | str | CEP extraido |
| vehicle_model | str | Modelo do veiculo |
| vehicle_year | str | Ano do veiculo |
| vehicle_color | str | Cor do veiculo |
| competitors_mentioned | list[str] | Concorrentes citados |
| competitor_price | float | Preco oferecido pela concorrencia |
| device | str | Dispositivo (da metadata) |
| city | str | Cidade |
| state | str | Estado |
| lead_source | str | Origem do lead |
| conversation_outcome | str | Resultado final |
| total_messages | int | Total de mensagens na conversa |
| lead_messages | int | Mensagens do lead |
| agent_messages | int | Mensagens do vendedor |
| first_message_at | datetime | Inicio da conversa |
| last_message_at | datetime | Ultima mensagem |
| conversation_duration_hours | float | Duracao total |

#### 3.2.3 Tabela: `conversations_enriched` -- Conversas com Metricas

Uma linha por `conversation_id` com metricas de interacao calculadas.

| Coluna | Calculo |
|--------|---------|
| avg_response_time_sec | Media de response_time_sec da metadata |
| pct_business_hours | % de mensagens em horario comercial |
| has_audio | Conversa contem transcricao de audio |
| has_media | Conversa contem imagem/video/doc |
| msg_count_bucket | cold(2-4), short(5-10), medium(11-20), long(21+) |
| lead_engagement_ratio | lead_messages / total_messages |
| first_response_time | Tempo entre 1a msg outbound e 1a msg inbound |

---

### 3.3 Gold Layer -- Tabelas Analiticas

#### 3.3.1 `gold_funnel_analysis` -- Funil de Conversao

**Objetivo**: Visualizar o pipeline de vendas como funil, do primeiro contato ate a conversao ou perda.

```
Conversas totais: 15.000
  |
  |--> Cold/Bounce (ghosting): 26.523 msgs (~1.767 convs estimadas a ~15 msgs)
  |--> Desistencia Lead: 20.002 msgs
  |--> Perdido Preco: 14.043 msgs
  |--> Perdido Concorrente: 19.465 msgs
  |--> Proposta Enviada: 18.836 msgs
  |--> Em Negociacao: 19.211 msgs
  |--> Venda Fechada: 35.148 msgs
```

Metricas por etapa:
- Taxa de conversao por campanha (`campaign_id`)
- Taxa de conversao por vendedor (`agent_id`)
- Tempo medio ate fechamento por outcome
- Distribuicao de outcomes por lead_source

#### 3.3.2 `gold_agent_performance` -- Desempenho dos Vendedores

**Objetivo**: Ranquear os 20 agentes por metricas de eficacia.

| Metrica | Calculo |
|---------|---------|
| total_conversations | Contagem de conversas unicas |
| win_rate | % venda_fechada / total_conversations |
| avg_messages_to_close | Media de mensagens ate venda_fechada |
| avg_response_time | Media de response_time_sec |
| ghosting_rate | % de conversas que terminaram em ghosting |
| competitor_loss_rate | % perdido_concorrente |
| price_loss_rate | % perdido_preco |
| avg_conversation_duration | Duracao media das conversas |
| engagement_score | Composto: tempo resposta, win_rate, ghosting inverso |
| messages_per_hour | Produtividade do agente |

Isso permite identificar: quem e o melhor vendedor, quem precisa de treinamento, quem tem problemas de ghosting (possivelmente demora para responder).

#### 3.3.3 `gold_sentiment_analysis` -- Sentimento por Mensagem/Conversa

**Abordagem de Sentimento** -- 3 opcoes em ordem de complexidade:

**Opcao A (Recomendada para MVP): Heuristica baseada em regras pt-BR**

```python
POSITIVE_SIGNALS = [
    "vamos fechar", "quero sim", "pode fazer", "fechado",
    "otimo", "perfeito", "excelente", "gostei", "aceito",
    "bom preco", "vou contratar", "manda o pix", "manda o link",
]

NEGATIVE_SIGNALS = [
    "caro", "muito caro", "nao quero", "desisto", "vou pensar",
    "achei caro", "nao tenho interesse", "ja fechei com",
    "nao preciso", "obrigado mas", "sem condicoes",
    "concorrente ofereceu menos", "hdi me cobrou menos",
]

HESITATION_SIGNALS = [
    "vou pensar", "nao sei", "hmm", "sera que", "deixa eu ver",
    "preciso conversar", "vou falar com", "depois te falo",
]
```

Calcular `sentiment_score` de -1.0 a +1.0 por mensagem, e agregar por conversa usando media ponderada (mensagens mais recentes tem peso maior -- indicam a tendencia final).

**Opcao B (Diferencial): Modelo pre-treinado**

Usar `pysentimiento` (modelo BERT treinado em pt-BR para analise de sentimento) ou `transformers` com modelo `nlptown/bert-base-multilingual-uncased-sentiment`.

```python
from pysentimiento import create_analyzer
analyzer = create_analyzer(task="sentiment", lang="pt")
result = analyzer.predict("achei caro demais, vou fechar com a HDI")
# -> SentimentOutput(output='NEG', probas={...})
```

Custo: ~2-3 min para processar 150k mensagens em CPU. Aceitavel para pipeline batch.

**Opcao C (Avancada): LLM local com Ollama**

Usar um LLM pequeno (Phi-3, Llama 3.1 8B) para classificacao de sentimento com prompt zero-shot. Mais lento, mas mais preciso para contexto de vendas de seguro.

**Recomendacao**: Implementar Opcao A primeiro (rapido, sem dependencias pesadas), depois Opcao B como upgrade. Opcao C e diferencial se houver tempo.

#### 3.3.4 `gold_lead_scoring` -- Pontuacao de Leads

**Objetivo**: Classificar leads por probabilidade de conversao, permitindo priorizacao.

| Feature | Peso | Logica |
|---------|------|--------|
| Engagement ratio | 0.20 | lead_messages / total > 0.4 = alto engajamento |
| Resposta rapida | 0.15 | first_response_time < 5min = alto interesse |
| Forneceu dados pessoais | 0.20 | CPF + email + telefone = intencao real |
| Forneceu dados veiculo | 0.15 | Placa + modelo + ano = pronto para cotar |
| Sem mencao a concorrente | 0.10 | Nao compara preco = menos sensivel |
| Horario comercial | 0.05 | Interagiu em horario util |
| Sentimento positivo | 0.15 | Sentiment_score > 0.3 |

Score final de 0-100, com buckets: `hot` (75+), `warm` (50-74), `cold` (25-49), `dead` (0-24).

Validacao: Comparar distribuicao de scores com `conversation_outcome` real. Se a maioria dos `venda_fechada` tem score alto, o modelo esta calibrado.

#### 3.3.5 `gold_email_providers` -- Distribuicao de Provedores de Email

Extrair dominio dos emails: `@gmail.com`, `@hotmail.com`, `@outlook.com`, `@yahoo.com.br`, dominios corporativos.

Valor analitico: entender se leads usam email pessoal vs. corporativo (indica perfil B2C vs. B2B).

#### 3.3.6 `gold_temporal_analysis` -- Horario Otimo de Contato

**Objetivo**: Determinar os melhores horarios e dias da semana para contatar leads.

```python
# PySpark: cruzar timestamp das primeiras respostas inbound com conversion
from pyspark.sql import functions as F

df_temporal = (
    spark.table("silver.conversations_enriched")
    .withColumn("contact_hour", F.hour("first_message_at"))
    .withColumn("contact_weekday", F.dayofweek("first_message_at"))
    .groupBy("contact_hour", "contact_weekday")
    .agg(
        F.count("*").alias("total_contacts"),
        F.sum(F.when(F.col("conversation_outcome") == "venda_fechada", 1).otherwise(0)).alias("wins"),
    )
    .withColumn("conversion_rate", F.col("wins") / F.col("total_contacts"))
)
```

Isso gera um heatmap de conversao por hora x dia da semana.

#### 3.3.7 `gold_competitor_intelligence` -- Inteligencia Competitiva

**Objetivo**: Mapear quais concorrentes sao mais mencionados, com que precos, e em quais conversas resultam em perda.

| Metrica | Descricao |
|---------|-----------|
| competitor_name | Seguradora mencionada |
| mention_count | Vezes mencionada no total |
| avg_competitor_price | Preco medio citado |
| loss_rate_when_mentioned | % de perdas quando o lead menciona esse concorrente |
| common_campaigns | Campanhas onde o concorrente aparece mais |
| price_delta_estimate | Diferenca estimada de preco (quando ambos precos disponiveis) |

#### 3.3.8 `gold_campaign_roi` -- Eficacia de Campanhas

**Objetivo**: Avaliar o ROI relativo de cada uma das 10 campanhas.

| Metrica | Descricao |
|---------|-----------|
| campaign_id | Identificador da campanha |
| total_leads | Total de conversas geradas |
| conversion_rate | % venda_fechada |
| avg_messages_to_convert | Eficiencia da campanha |
| lead_quality_score | Media do lead_scoring dos leads gerados |
| top_agent | Melhor vendedor nesta campanha |
| dominant_source | Fonte de lead mais comum (google_ads, etc.) |
| avg_conversation_duration | Tempo medio de negociacao |
| ghosting_rate | Taxa de abandono |

#### 3.3.9 `gold_persona_classification` -- Classificacao de Personas

**Objetivo**: Agrupar leads em personas de comportamento para segmentacao.

Personas propostas baseadas nos dados:

| Persona | Criterios |
|---------|-----------|
| **Decidido Rapido** | < 5 mensagens, venda_fechada, response_time < 2min |
| **Comparador de Preco** | Menciona concorrente, pede desconto, perdido_preco ou perdido_concorrente |
| **Engajado Indeciso** | 15+ mensagens, em_negociacao ou proposta_enviada, sentimento oscilante |
| **Ghost** | < 4 mensagens inbound, ghosting, response_time alto ou nulo |
| **Lead Quente** | Forneceu CPF/placa/email, sentimento positivo, venda_fechada ou em_negociacao |
| **Curioso** | Muitas perguntas (mensagens terminando em "?"), desistencia_lead |

Implementacao: Regras deterministicas primeiro, clusterizacao (K-Means sobre features numericas do lead_scoring) como upgrade.

---

## 4. Design do Agente Autonomo

O agente sao **dois notebooks Databricks** — `agent_pre.py` (Task 0) e `agent_post.py` (Task 5). Vivem inteiramente dentro do Databricks — nao existe processo local em producao.

### 4.1 Papel do Agente

O agente e dividido em **duas tasks**: Task 0 (pre-check) e Task 5 (post-check + recovery + notificacao).

```
Databricks Workflow (cron diario, max_concurrent_runs = 1)
  |
  +-> Task 0: AGENTE PRE-CHECK (notebooks/agent_pre.py)
  |     +-- 1. Consulta estado anterior (Delta Table: pipeline.state)
  |     +-- 2. Verifica se ha dados novos no S3 (via metadata)
  |     +-- 3. Se nao ha: seta should_process=false, encerra
  |     +-- 4. Se ha: seta task values, registra versoes Delta atuais (para rollback)
  |
  +-> Task 1: Bronze Ingestion       (depende de Task 0, condicao: should_process=true)
  +-> Task 2a: Silver Dedup+Clean    (depende de Task 1)
  +-> Task 2b: Silver Entities+Mask  (depende de Task 2a)
  +-> Task 2c: Silver Enrichment     (depende de Task 2a)
  +-> Task 3: Gold Analytics          (depende de Task 2b + 2c)
  +-> Task 4: Quality Validation      (depende de Task 3)
  |
  +-> Task 5: AGENTE POST-CHECK (notebooks/agent_post.py)
        +-- 1. Verifica resultados de todas as tasks
        +-- 2. Se TUDO OK: persiste estado SUCCESS, envia email de resumo
        +-- 3. Se falha detectada: tenta correcao (retry task, rollback Delta)
        +-- 4. Se correcao OK: persiste estado RECOVERED, envia email com resumo da correcao
        +-- 5. Se correcao falha (guardrail): persiste estado FAILED, envia email CRITICO
        +-- Task 5 roda SEMPRE (run_if: ALL_DONE — executa mesmo se tasks anteriores falharem)
```

O agente **nao processa dados** — ele orquestra. As transformacoes ficam nos notebooks de cada camada.

**Silver desacoplada**: A Silver agora e 3 tasks independentes:
- **Task 2a**: Dedup + limpeza de nomes + parse metadata → `silver.messages_clean`
- **Task 2b**: Extracao de entidades + mascaramento + redaction do message_body → `silver.leads_profile` (depende de 2a)
- **Task 2c**: Enriquecimento de conversas (metricas por conversa) → `silver.conversations_enriched` (depende de 2a, paralela com 2b)

Se Task 2b falhar, Task 2a nao e perdida. Se Task 2c falhar, 2a e 2b continuam validas.

### 4.2 Implementacao do Agente

```python
# notebooks/agent_pre.py — roda como Task 0 do Databricks Workflow
import logging
from datetime import datetime
from delta.tables import DeltaTable

logger = logging.getLogger("pipeline_agent")

# ============================================================
# 1. CARREGAR ESTADO ANTERIOR
# ============================================================
STATE_TABLE = "pipeline.state"

def load_state(spark) -> dict:
    """Carrega o estado da ultima execucao bem-sucedida."""
    if spark.catalog.tableExists(STATE_TABLE):
        row = spark.table(STATE_TABLE).orderBy("run_at", ascending=False).first()
        if row:
            return row.asDict()
    return {"last_bronze_hash": None, "last_run_at": None, "consecutive_failures": 0}

state = load_state(spark)
logger.info(f"Estado anterior: {state}")

# ============================================================
# 2. VERIFICAR DADOS NOVOS NO S3
# ============================================================
BRONZE_PATH = "s3://meu-bucket/bronze/"

def get_bronze_fingerprint(s3_path: str) -> str:
    """Detecta mudancas via metadados do S3 — O(1), sem ler o conteudo."""
    import hashlib
    files = dbutils.fs.ls(s3_path)
    fingerprint = "|".join(
        f"{f.name}:{f.size}:{f.modificationTime}"
        for f in sorted(files, key=lambda x: x.name)
    )
    return hashlib.sha256(fingerprint.encode()).hexdigest()

current_hash = get_bronze_fingerprint(BRONZE_PATH)
has_new_data = current_hash != state.get("last_bronze_hash")

if not has_new_data:
    logger.info("Sem dados novos. Encerrando workflow.")
    dbutils.jobs.taskValues.set(key="should_process", value=False)
    dbutils.notebook.exit("SKIP: no new data")

# ============================================================
# 3. REGISTRAR VERSOES DELTA ATUAIS (para rollback no agent_post)
# ============================================================
TRACKED_TABLES = [
    "bronze.conversations",
    "silver.messages_clean", "silver.leads_profile", "silver.conversations_enriched",
    "gold.funil_vendas", "gold.agent_performance", "gold.sentiment",
    "gold.lead_scoring", "gold.competitor_intel", "gold.campaign_roi",
    "gold.personas", "gold.temporal_analysis", "gold.email_providers",
    "gold.churn_reengagement", "gold.negotiation_complexity", "gold.first_contact_resolution",
]

def capture_delta_versions(spark, tables: list) -> dict:
    """Captura a versao atual de cada Delta Table para possivel rollback."""
    versions = {}
    for table in tables:
        try:
            if spark.catalog.tableExists(table):
                history = spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first()
                versions[table] = history["version"]
        except Exception:
            pass  # Tabela ainda nao existe (primeira execucao)
    return versions

delta_versions = capture_delta_versions(spark, TRACKED_TABLES)
logger.info(f"Versoes Delta capturadas: {delta_versions}")

# ============================================================
# 4. SETAR TASK VALUES PARA TASKS DOWNSTREAM
# ============================================================
import json

logger.info(f"Dados novos detectados! Hash: {current_hash}")
dbutils.jobs.taskValues.set(key="should_process", value=True)
dbutils.jobs.taskValues.set(key="bronze_path", value=BRONZE_PATH)
dbutils.jobs.taskValues.set(key="bronze_hash", value=current_hash)
dbutils.jobs.taskValues.set(key="run_id", value=datetime.now().isoformat())
dbutils.jobs.taskValues.set(key="delta_versions", value=json.dumps(delta_versions))

# ============================================================
# 3. PERSISTIR ESTADO (sera chamado novamente apos as tasks)
# ============================================================
def save_state(spark, bronze_hash: str, status: str, failures: int):
    """Persiste estado da execucao em Delta Table."""
    from pyspark.sql import Row
    new_state = Row(
        run_at=datetime.now().isoformat(),
        last_bronze_hash=bronze_hash,
        status=status,
        consecutive_failures=failures,
    )
    spark.createDataFrame([new_state]).write \
        .format("delta") \
        .mode("append") \
        .saveAsTable(STATE_TABLE)
```

### 4.3 Como as Tasks Downstream Respeitam o Agente

Cada task do Workflow consulta o `task value` setado pelo agente:

```python
# No inicio de cada notebook (bronze/ingest.py, silver/dedup_clean.py, etc.)
should_process = dbutils.jobs.taskValues.get(
    taskKey="agent_pre", key="should_process", default=False
)
if not should_process:
    dbutils.notebook.exit("SKIP: agent decided no processing needed")

bronze_path = dbutils.jobs.taskValues.get(taskKey="agent_pre", key="bronze_path")
run_id = dbutils.jobs.taskValues.get(taskKey="agent_pre", key="run_id")

# ... processamento normal da camada
```

### 4.4 Estrategia de Auto-Correcao e Notificacoes

O agente opera em **dois niveis**: o Workflow faz retries por task (nivel 1), e o agent_post.py faz recovery inteligente + notificacao (nivel 2).

| Tipo de Falha | Nivel | Deteccao | Correcao | Email |
|---------------|-------|----------|----------|-------|
| **Task falha por erro transiente** | 1 (Workflow) | Databricks detecta | Retry automatico (2x por task) | Nenhum (retry transparente) |
| **Arquivo Bronze corrompido** | 2 (Agente) | Schema validation falha | Rollback Bronze Delta para versao anterior | CRITICO |
| **Schema com colunas obrigatorias faltando** | 2 (Agente) | Validacao no notebook Bronze | Nao propaga para Silver + rollback | CRITICO |
| **Regex falha em texto inesperado** | 1 (Task) | try/except no notebook Silver | Skip da mensagem + log | Resumo (X mensagens com erro) |
| **Tabela Gold com 0 linhas** | 2 (Agente) | Quality validation detecta | Re-trigger tasks Gold | CORRECAO se OK, CRITICO se falha |
| **Silver parcial falha** | 2 (Agente) | Task 2b ou 2c falhou | Re-trigger apenas a task que falhou (2a preservada) | CORRECAO/CRITICO |
| **3+ falhas consecutivas** | 2 (Agente) | `consecutive_failures >= 3` | PARA de tentar, aguarda intervencao | CRITICO |
| **Colunas novas no Bronze** | 1 (Task) | Delta `mergeSchema` | Aceita automaticamente | INFO (resumo de colunas novas) |

#### Implementacao do agent_post.py (Task 5)

```python
# notebooks/agent_post.py — Task 5: roda SEMPRE (run_if: ALL_DONE)
import logging
from datetime import datetime

logger = logging.getLogger("agent_post")

# ============================================================
# 1. COLETAR RESULTADOS DE TODAS AS TASKS
# ============================================================
def collect_task_results() -> dict:
    """Coleta status de cada task via taskValues."""
    tasks = ["bronze_ingestion", "silver_dedup", "silver_entities", 
             "silver_enrichment", "gold_analytics", "quality_validation"]
    results = {}
    for task in tasks:
        try:
            results[task] = dbutils.jobs.taskValues.get(
                taskKey=task, key="status", default="UNKNOWN"
            )
        except Exception:
            results[task] = "FAILED"  # Se nao conseguiu ler, assumir falha
    return results

# ============================================================
# 2. DECIDIR ACAO: SUCESSO, CORRECAO, OU FALHA
# ============================================================
task_results = collect_task_results()
state = load_state(spark)
current_hash = dbutils.jobs.taskValues.get(taskKey="agent_pre", key="bronze_hash")
should_process = dbutils.jobs.taskValues.get(taskKey="agent_pre", key="should_process", default=False)
delta_versions = json.loads(
    dbutils.jobs.taskValues.get(taskKey="agent_pre", key="delta_versions", default="{}")
)

# Se nao havia dados novos, apenas registrar skip
if not should_process:
    save_state(spark, state.get("last_bronze_hash"), "SKIP", 0)
    dbutils.notebook.exit("SKIP: no new data")

failed_tasks = [t for t, s in task_results.items() if s != "SUCCESS"]
all_ok = len(failed_tasks) == 0

if all_ok:
    # ============================================================
    # CENARIO 1: TUDO OK — email de resumo
    # ============================================================
    save_state(spark, current_hash, "SUCCESS", consecutive_failures=0)
    send_email(
        subject="[Pipeline Medallion] Execucao concluida com sucesso",
        body=build_success_summary(task_results),
        level="INFO",
    )
    dbutils.notebook.exit("SUCCESS")

# ============================================================
# CENARIO 2: FALHA DETECTADA — tentar correcao
# ============================================================
logger.warning(f"Tasks com falha: {failed_tasks}")
failures = state.get("consecutive_failures", 0) + 1

# Guardrail: se ja falhou 3+ vezes, NAO tentar corrigir
if failures >= 3:
    save_state(spark, current_hash, "FAILED", consecutive_failures=failures)
    send_email(
        subject="[Pipeline Medallion] CRITICO - Falha persistente, intervencao necessaria",
        body=build_critical_summary(task_results, failures),
        level="CRITICAL",
    )
    dbutils.notebook.exit(f"CRITICAL: {failures} consecutive failures")

# Tentar correcao
try:
    recovery_actions = attempt_recovery(spark, failed_tasks, delta_versions)
    
    # Se recovery funcionou
    save_state(spark, current_hash, "RECOVERED", consecutive_failures=0)
    send_email(
        subject="[Pipeline Medallion] Correcao automatica realizada com sucesso",
        body=build_recovery_summary(failed_tasks, recovery_actions),
        level="WARNING",
    )
    dbutils.notebook.exit("RECOVERED")

except Exception as recovery_error:
    # ============================================================
    # CENARIO 3: CORRECAO FALHOU — guardrail final
    # ============================================================
    logger.error(f"Recovery falhou: {recovery_error}")
    save_state(spark, current_hash, "FAILED", consecutive_failures=failures)
    send_email(
        subject="[Pipeline Medallion] FALHA - Correcao automatica nao funcionou",
        body=build_failure_summary(task_results, recovery_error, failures),
        level="CRITICAL",
    )
    dbutils.notebook.exit(f"FAILED: recovery error - {recovery_error}")

# ============================================================
# FUNCOES DE RECOVERY
# ============================================================
def attempt_recovery(spark, failed_tasks: list, delta_versions: dict) -> list:
    """Tenta corrigir tasks com falha. Retorna lista de acoes tomadas."""
    actions = []
    
    for task in failed_tasks:
        if task == "bronze_ingestion":
            # Rollback Bronze Delta para versao anterior
            version = delta_versions.get("bronze.conversations")
            if version is not None:
                spark.sql(f"RESTORE TABLE bronze.conversations TO VERSION AS OF {version}")
                actions.append(f"Rollback bronze.conversations para versao {version}")
            else:
                raise Exception("Sem versao anterior para rollback do Bronze")
        
        elif task.startswith("silver_"):
            # Rollback tabela Silver afetada
            table = TASK_TO_TABLE.get(task)
            version = delta_versions.get(table)
            if version and table:
                spark.sql(f"RESTORE TABLE {table} TO VERSION AS OF {version}")
                actions.append(f"Rollback {table} para versao {version}")
        
        elif task == "gold_analytics":
            # Re-calcular Gold e viavel se Silver esta ok
            silver_ok = all(s == "SUCCESS" for t, s in collect_task_results().items() if t.startswith("silver_"))
            if silver_ok:
                dbutils.notebook.run("/notebooks/gold/analytics", timeout_seconds=600)
                actions.append("Re-executou gold/analytics.py com sucesso")
            else:
                raise Exception("Silver com falha, nao pode recalcular Gold")
        
        elif task == "quality_validation":
            # Validation falhou = dados podem estar inconsistentes
            # Rollback todas as tabelas Gold para versao anterior
            for table, version in delta_versions.items():
                if table.startswith("gold."):
                    spark.sql(f"RESTORE TABLE {table} TO VERSION AS OF {version}")
                    actions.append(f"Rollback {table} para versao {version}")
    
    return actions

# ============================================================
# FUNCOES DE EMAIL
# ============================================================
def send_email(subject: str, body: str, level: str):
    """Envia notificacao via Databricks notification ou webhook."""
    # Opcao 1: Usar dbutils.notebook.exit com mensagem estruturada
    #          + Databricks Workflow email_notifications
    # Opcao 2: Webhook direto para servico de email (SendGrid, SES, etc.)
    # Opcao 3: Escrever em Delta Table de notificacoes + job separado que envia
    import json
    notification = {
        "timestamp": datetime.now().isoformat(),
        "subject": subject,
        "body": body,
        "level": level,
    }
    # Persistir notificacao para auditoria
    spark.createDataFrame([notification]).write \
        .format("delta").mode("append").saveAsTable("pipeline.notifications")
    
    # Enviar via webhook (ex: AWS SES ou SendGrid)
    # requests.post(WEBHOOK_URL, json=notification)
    logger.info(f"Notificacao enviada: {subject}")
```

#### Tipos de Email por Cenario

| Cenario | Subject | Conteudo |
|---------|---------|----------|
| **Sucesso** | `[Pipeline] Execucao concluida com sucesso` | Resumo: linhas processadas por camada, tempo total, tabelas Gold atualizadas |
| **Correcao automatica** | `[Pipeline] Correcao automatica realizada` | Quais tasks falharam, o que foi feito (rollback, re-run), resultado final |
| **Falha (correcao nao funcionou)** | `[Pipeline] FALHA - Correcao nao funcionou` | Tasks com erro, tentativa de correcao, por que falhou, `consecutive_failures` |
| **Falha critica (3+ consecutivas)** | `[Pipeline] CRITICO - Intervencao necessaria` | Historico de falhas, diagnostico, agente PAROU de tentar |
| **Schema evolution** | `[Pipeline] INFO - Novas colunas detectadas` | Lista de colunas novas no Bronze, propagadas automaticamente |

### 4.5 Estado Persistente (Delta Table)

Em vez de JSON no filesystem, o agente persiste estado em uma **Delta Table**:

```sql
-- pipeline.state (Delta Table no Unity Catalog)
CREATE TABLE IF NOT EXISTS pipeline.state (
    run_at                STRING,
    last_bronze_hash      STRING,
    status                STRING,      -- SUCCESS | FAILED | SKIP | RECOVERED
    consecutive_failures  INT,
    delta_versions        STRING       -- JSON com versao de cada tabela antes do run
)
USING DELTA;

-- Consultas uteis:
-- Ultimo estado
SELECT * FROM pipeline.state ORDER BY run_at DESC LIMIT 1;

-- Historico de falhas
SELECT * FROM pipeline.state WHERE status = 'FAILED' ORDER BY run_at DESC;
```

Vantagens sobre JSON: auditavel, versionado (Delta time travel), consultavel via SQL, sem risco de corrupcao por escrita concorrente.

---

## 5. Stack Tecnologica Recomendada

### 5.1 Stack Core: Databricks + AWS

| Componente | Uso | Justificativa |
|------------|-----|---------------|
| **Databricks Workspace (AWS)** | Plataforma de execucao | Workflows nativos para orquestracao, compute serverless, Unity Catalog para governanca. E o ambiente de producao do pipeline. |
| **Delta Lake** | Formato de armazenamento | ACID transactions, schema evolution nativo (`mergeSchema`), time travel, audit history. Padrao do Databricks. |
| **AWS S3** | Data lake storage | Armazenamento das 3 camadas. Integracao nativa com Databricks. Event notifications para trigger de pipeline. |
| **PySpark** | Processamento de dados | Engine nativa do Databricks. Distribuido, escala horizontal automatica. Lazy evaluation. SQL + DataFrame API. |
| **Databricks Workflows** | Orquestracao e agendamento | DAG de tasks com dependencias, retries automaticos, alertas, trigger por file arrival ou cron. Substitui APScheduler/watchdog. |
| **Unity Catalog** | Governanca de dados | Schema registry, linhagem, controle de acesso, auditoria. Tabelas Bronze/Silver/Gold registradas e rastreadas. |

### 5.1.1 Bibliotecas Python Complementares

| Biblioteca | Uso | Justificativa |
|------------|-----|---------------|
| **Pydantic v2** | Validacao de schemas na `lib/` | Validacao tipada dos contratos de dados. Testavel localmente. |
| **logging** (stdlib) | Logs nos notebooks | Databricks captura logs automaticamente. `logging` padrao e suficiente, sem dependencias extras. |
| **dbutils** (nativo) | Comunicacao entre tasks | `taskValues` para passar dados entre agente e tasks. `notebook.exit()` para controle de fluxo. |

### 5.2 Por que PySpark no Databricks (e nao Polars/Pandas local)

**PySpark e a escolha natural** porque o pipeline roda no Databricks:

1. **Nativo do Databricks**: Sem fricao de setup. Spark session ja disponivel. Delta Lake integrado. Unity Catalog funciona out-of-the-box.

2. **Schema evolution nativo**: Delta Lake com `mergeSchema=true` aceita colunas novas automaticamente. Exatamente o que precisamos para escala horizontal.

3. **Escala sem refatoracao**: 153k linhas e pequeno, mas se o dataset crescer 100x o codigo nao muda. Spark distribui automaticamente.

4. **SQL + DataFrame API**: Permite escrever transformacoes em PySpark DataFrame ou em SQL puro (Databricks SQL). Flexibilidade para Gold layer.

```python
# PySpark: dedup + group_by + agg no Databricks
from pyspark.sql import functions as F

result = (
    spark.table("silver.messages_clean")
    .filter(F.col("direction") == "inbound")
    .groupBy("conversation_id")
    .agg(
        F.collect_set(F.regexp_extract("message_body", CPF_PATTERN, 0)).alias("cpfs"),
        F.first("sender_name").alias("lead_name"),
    )
)
result.write.format("delta").mode("overwrite").saveAsTable("gold.leads_summary")
```

5. **Delta Lake para todas as camadas**: ACID, time travel, schema enforcement com evolution, audit log. Cada camada e uma Delta Table no Unity Catalog.

**Desenvolvimento local**: Para testes e desenvolvimento rapido, usar `polars` ou `pandas` localmente. O deploy final roda em PySpark no Databricks. O agente Python cuida do deploy e gerenciamento.

### 5.3 Bibliotecas Complementares

| Biblioteca | Uso | Justificativa |
|------------|-----|---------------|
| **pysentimiento** | Sentimento em pt-BR | Modelo BERT pre-treinado para portugues. Pode rodar como UDF no Spark ou pre-processar localmente. |
| **scikit-learn** | Clusterizacao de personas | K-Means para segmentacao nao-supervisionada. Pode rodar como UDF Spark ou em notebook separado. |
| **rich** | Terminal output local | Para desenvolvimento/debug local. |

### 5.4 Gerenciamento de Dependencias

Recomendacao: **`uv`** como gerenciador de pacotes (substitui pip, muito mais rapido) com `pyproject.toml`.

```toml
[project]
name = "medallion-pipeline"
version = "0.1.0"
requires-python = ">=3.11"
# Dependencias minimas: lib/ (roda local e no Databricks como wheel)
dependencies = [
    "pydantic>=2.0",
]

[project.optional-dependencies]
ml = ["pysentimiento>=0.7", "scikit-learn>=1.4"]
dev = ["pytest>=8.0", "ruff>=0.4", "pyspark>=3.5", "delta-spark>=3.0"]
```

**Nota**: PySpark, Delta Lake, dbutils, e logging vem **pre-instalados** no Databricks Runtime. O `pyproject.toml` define apenas o que a `lib/` precisa para testes locais e para build do wheel.

---

## 6. Estrategia de Dados Sensiveis

### 6.1 Principios

1. **Mascaramento irreversivel**: Dados mascarados nao podem ser revertidos ao original
2. **Preservacao de dimensoes**: O dado mascarado mantem o mesmo formato/tamanho
3. **Consistencia**: O mesmo CPF mascarado sempre gera a mesma saida (determinismo via HMAC)
4. **Utilidade analitica**: Dados mascarados ainda permitem agrupamento e contagem

### 6.2 Estrategia por Tipo de Dado

**CPF**: Mascaramento parcial + hash consistente

```python
import hmac
import hashlib

SECRET_KEY = os.environ["MASKING_SECRET"]  # OBRIGATORIO — falha se nao configurado
# Nunca usar fallback/default. Mascaramento com chave previsivel e equivalente a nao mascarar.

def mask_cpf(cpf: str) -> str:
    """
    '418.696.561-30' -> '***.***.561-30'
    Preserva ultimos 5 digitos para agrupamento parcial.
    Hash completo armazenado separadamente para joins futuros.
    """
    digits = re.sub(r'\D', '', cpf)
    if len(digits) != 11:
        return "***.***.***-**"
    masked = f"***.***{digits[6:9]}-{digits[9:]}"
    return masked

def hash_cpf(cpf: str) -> str:
    """Hash HMAC-SHA256 do CPF normalizado para joins deterministicos."""
    digits = re.sub(r'\D', '', cpf)
    return hmac.new(SECRET_KEY.encode(), digits.encode(), hashlib.sha256).hexdigest()[:16]
```

**Email**: Preservar dominio, mascarar usuario

```python
def mask_email(email: str) -> str:
    """
    'joao.silva@gmail.com' -> 'j***a@gmail.com'
    Preserva dominio para analise de provedores.
    """
    user, domain = email.split('@')
    if len(user) <= 2:
        masked_user = '*' * len(user)
    else:
        masked_user = user[0] + '*' * (len(user) - 2) + user[-1]
    return f"{masked_user}@{domain}"
```

**Telefone**: Mascarar digitos centrais

```python
def mask_phone(phone: str) -> str:
    """
    '(11) 98765-4321' -> '(11) ****-4321'
    Preserva DDD e ultimos 4 digitos.
    """
    digits = re.sub(r'\D', '', phone)
    if len(digits) >= 10:
        return f"({digits[:2]}) ****-{digits[-4:]}"
    return "(**) ****-****"
```

**Placa**: Mascarar parcialmente

```python
def mask_plate(plate: str) -> str:
    """
    'SYL8V26' -> 'S**8*26'
    Preserva formato mas impede identificacao.
    """
    clean = re.sub(r'[^A-Za-z0-9]', '', plate).upper()
    if len(clean) == 7:
        return f"{clean[0]}**{clean[3]}*{clean[5:]}"
    return "***-****"
```

**Nome**: Nao mascarar no Silver (necessario para normalizacao), mascarar no Gold se exportado

### 6.3 Onde Aplicar o Mascaramento

O mascaramento ocorre **na etapa Silver**, em dois pontos:

1. **Colunas estruturadas** (`cpf_extracted`, `email_extracted`, etc.): mascaramento na extracao
2. **`message_body` (texto livre)**: **redaction** — substituir matches de regex no corpo da mensagem pelas versoes mascaradas

```
Bronze (original)
  -> Extrator (identifica CPF no message_body)
  -> Mascarador (mascara colunas estruturadas)
  -> Redactor (substitui CPF/email/phone/placa no message_body por versao mascarada)
  -> Silver (persistido: colunas mascaradas + message_body sanitizado)
```

**Redaction do message_body**:

```python
def redact_message_body(body: str) -> str:
    """Substitui dados sensiveis no texto livre por versoes mascaradas."""
    if not body:
        return body
    # Aplicar redaction em cascata (ordem importa: CPF antes de telefone)
    for pattern_name, pattern in [("cpf", CPF_PATTERN), ("email", EMAIL_PATTERN),
                                   ("phone", PHONE_PATTERN), ("plate", PLATE_PATTERN)]:
        body = re.sub(pattern, lambda m: MASK_FN[pattern_name](m.group()), body)
    return body
```

Isso garante que `silver.messages_clean` **nao contenha dados sensiveis em texto claro**, nem em colunas estruturadas nem no corpo da mensagem.

O Parquet cru no S3 `/bronze/` mantem os dados originais. O acesso ao Bronze deve ser restrito via Unity Catalog (column-level security ou table ACLs) e o bucket S3 deve ter criptografia at-rest (SSE-S3 ou SSE-KMS).

### 6.4 Tabela de Mapeamento (Opcional, Segura)

Se for necessario reverter mascaramento para auditoria:

```
data/secure/
  |-- mapping.encrypted  # Mapeamento hash -> original, criptografado com Fernet
```

Usar `cryptography.Fernet` para criptografar o mapeamento com chave derivada de variavel de ambiente. Este arquivo nunca vai para Git.

---

## 6.5 Observabilidade no Databricks

Tudo roda dentro do Databricks, entao a observabilidade usa **recursos nativos** da plataforma:

### Metricas do Pipeline (Delta Table)

Cada task registra metricas em uma Delta Table `pipeline.metrics`:

```python
# No final de cada notebook de camada
def log_metrics(spark, task_name: str, metrics: dict):
    from pyspark.sql import Row
    row = Row(
        task=task_name,
        run_id=run_id,
        timestamp=datetime.now().isoformat(),
        rows_input=metrics.get("rows_input", 0),
        rows_output=metrics.get("rows_output", 0),
        rows_error=metrics.get("rows_error", 0),
        duration_sec=metrics.get("duration_sec", 0),
        extraction_miss_rate=metrics.get("extraction_miss_rate", 0.0),
    )
    spark.createDataFrame([row]).write.format("delta").mode("append").saveAsTable("pipeline.metrics")
```

### Databricks SQL Dashboard

Criar um dashboard no Databricks SQL com queries sobre as Delta Tables de estado e metricas:

| Painel | Query |
|--------|-------|
| **Status ultimo run** | `SELECT * FROM pipeline.state ORDER BY run_at DESC LIMIT 1` |
| **Historico de falhas** | `SELECT run_at, status, consecutive_failures FROM pipeline.state WHERE status = 'FAILED'` |
| **Linhas processadas por camada** | `SELECT task, SUM(rows_output) FROM pipeline.metrics GROUP BY task` |
| **Taxa de erro de extracao** | `SELECT AVG(extraction_miss_rate) FROM pipeline.metrics WHERE task = 'silver_entities'` |
| **Tempo por etapa** | `SELECT task, AVG(duration_sec) FROM pipeline.metrics GROUP BY task` |
| **Notificacoes enviadas** | `SELECT * FROM pipeline.notifications ORDER BY timestamp DESC LIMIT 20` |

### Alertas Databricks

Usar **Databricks SQL Alerts** para monitoramento proativo:

- **Alert 1**: `SELECT consecutive_failures FROM pipeline.state ORDER BY run_at DESC LIMIT 1` — disparar se > 0
- **Alert 2**: `SELECT COUNT(*) FROM pipeline.metrics WHERE rows_error > 0 AND timestamp > current_date()` — erros hoje
- **Alert 3**: `SELECT DATEDIFF(current_timestamp(), MAX(run_at)) FROM pipeline.state WHERE status = 'SUCCESS'` — dias sem sucesso

Esses alertas complementam os emails do agent_post.py e permitem monitoramento visual.

---

## 7. Diferenciais Competitivos

### 7.1 Insights Gold que Vao Alem do Pedido

O enunciado sugere: distribuicao de provedores de email, personas, segmentacao, sentimento. Aqui estao os **diferenciais criativos**:

#### 7.1.1 Analise de Funil com Gargalos

Nao apenas contar outcomes, mas identificar **onde as conversas morrem**:

- Em qual mensagem (numero sequencial) o lead para de responder?
- Qual e a "mensagem fatal" mais comum antes de ghosting?
- Existe correlacao entre tipo de mensagem do agente e desistencia?

Isso transforma dados brutos em **insight acionavel para treinamento de vendedores**.

#### 7.1.2 Scoring de Agentes com Ranking Relativo

Nao apenas metricas absolutas, mas **percentis** entre os 20 agentes:

```
Agent_005: Win rate P90 (top 10%), Response time P20 (rapido),
           Ghosting rate P80 (alto) -> Diagnostico: "Bom vendedor,
           mas perde leads por demorar a fazer follow-up"
```

Incluir **recomendacoes automatizadas** por agente baseadas no perfil de metricas.

#### 7.1.3 Inteligencia Competitiva com Price Gap

Cruzar `competitor_price` com `conversation_outcome`:

- Quando o lead menciona preco da concorrencia e a venda fecha mesmo: qual era o delta?
- Qual concorrente causa mais perdas?
- Existe um "preco teto" acima do qual a perda e quase certa?

Isso gera **inteligencia de pricing real baseada em conversas**.

#### 7.1.4 Predicao de Outcome por Features Iniciais

Treinar um modelo simples (Logistic Regression ou Decision Tree) que preveja `conversation_outcome` usando apenas features das primeiras 3 mensagens:

- Hora do contato
- Lead source
- Tempo de resposta do lead
- Comprimento da primeira mensagem
- Presenca de saudacao vs. pergunta direta

Se funcionar, isso permite **triagem automatica de leads em tempo real**.

#### 7.1.5 Analise de Linguagem Natural do Vendedor

Quais palavras/frases o vendedor usa que correlacionam com vendas fechadas vs. perdidas?

```python
# TF-IDF nas mensagens outbound, agrupadas por outcome
# Palavras mais associadas a venda_fechada
# Palavras mais associadas a perdido_preco
```

Insight: "Vendedores que usam a palavra 'tranquilidade' fecham 23% mais que os que usam 'barato'."

#### 7.1.6 Mapa de Calor Geografico

Usando `city` e `state` da metadata:

- Quais estados/cidades tem maior taxa de conversao?
- Existe sazonalidade regional?
- Quais campanhas performam melhor em quais regioes?

#### 7.1.7 Analise de Device como Proxy de Comportamento

`device` da metadata (desktop vs. mobile):
- Leads mobile respondem mais rapido?
- Desktop tem tickets maiores?
- Ghosting e mais comum em mobile?

#### 7.1.8 Analise de Churn e Reengajamento

Identificar leads que pararam de responder por X horas mas depois voltaram:

- Quais mensagens do vendedor "reativaram" o lead?
- Qual o tempo medio de silencio antes do reengajamento?
- Reengajamento correlaciona com conversao?

Isso e **ouro para treinamento comercial** — saber quais mensagens funcionam para recuperar leads "mortos".

#### 7.1.9 Analise de Complexidade da Negociacao

Correlacionar numero de perguntas do lead (mensagens com "?") e tipo de perguntas com o outcome:

- Leads que perguntam mais convertem mais ou menos?
- Perguntas sobre preco vs. perguntas sobre cobertura: qual perfil converte melhor?
- Leads que pedem documentos (PDF de proposta) fecham mais?

#### 7.1.10 First Contact Resolution

Das vendas fechadas, quantas % foram resolvidas na primeira conversa vs. multiplos contatos?

Isso requer identificar o **mesmo lead em conversas diferentes** (via telefone/email hasheado). Se um lead aparece em 3 conversas e so fechou na terceira, o custo de aquisicao e muito maior.

| Metrica | Descricao |
|---------|-----------|
| first_contact_resolution_rate | % de vendas fechadas na 1a conversa |
| avg_contacts_to_close | Media de conversas ate fechar |
| recontact_conversion_lift | Quanto o recontato aumenta a conversao |

### 7.2 Estrutura do Databricks Workflow

O Workflow e o **coracao do pipeline**. Configurado via UI do Databricks ou via Terraform/API:

```
Workflow: medallion_pipeline_whatsapp
Trigger: Cron diario (0 0 6 * * ?)  -- 06:00 UTC
Cluster: single-node (i3.xlarge ou serverless)
max_concurrent_runs: 1

|
+-> Task 0: agent_pre (notebooks/agent_pre.py)
|     Retry: 1x
|     Papel: verifica dados novos, registra versoes Delta, seta task values
|
+-> Task 1: bronze_ingestion (depende de agent_pre)
|     Notebook: /notebooks/bronze/ingest.py
|     Retry: 2x
|     Condicao: {{tasks.agent_pre.values.should_process}} == true
|
+-> Task 2a: silver_dedup (depende de bronze_ingestion)
|     Notebook: /notebooks/silver/dedup_clean.py
|     Retry: 2x
|
+-> Task 2b: silver_entities (depende de silver_dedup)
|     Notebook: /notebooks/silver/entities_mask.py
|     Retry: 2x
|
+-> Task 2c: silver_enrichment (depende de silver_dedup, paralela com 2b)
|     Notebook: /notebooks/silver/enrichment.py
|     Retry: 2x
|
+-> Task 3: gold_analytics (depende de silver_entities + silver_enrichment)
|     Notebook: /notebooks/gold/analytics.py
|     Retry: 2x
|
+-> Task 4: quality_validation (depende de gold_analytics)
|     Notebook: /notebooks/validation/checks.py
|     Retry: 1x
|
+-> Task 5: agent_post (run_if: ALL_DONE — roda SEMPRE, mesmo se tasks falharam)
      Notebook: /notebooks/agent_post.py
      Retry: 0 (nao retentar — guardrail)
      Papel: verifica resultados, recovery, notificacoes, persiste estado
```

**Deploy dos notebooks**: Via **Databricks Repos** (sync automatico com GitHub). Push no GitHub -> notebooks atualizados no workspace. Sem necessidade de script de deploy.

### 7.3 Delta Lake como Formato Padrao

Todas as camadas usam **Delta Tables** no S3, gerenciadas pelo Unity Catalog:

```python
# Dentro de um notebook Databricks (PySpark)

# Bronze -> Silver com schema evolution
df_bronze = spark.table("bronze.conversations")

df_silver = transform_silver(df_bronze)  # dedup, clean, mask

# mergeSchema=true permite colunas novas automaticamente
(df_silver.write
    .format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")  # <<< schema evolution
    .saveAsTable("silver.messages_clean"))

# Time travel: consultar versao anterior
df_v2 = spark.read.format("delta").option("versionAsOf", 2).table("silver.messages_clean")

# Audit: ver historico de mudancas
spark.sql("DESCRIBE HISTORY silver.messages_clean").show()
```

**Por que Delta Lake e nao Parquet puro**:
- Schema evolution nativo (`mergeSchema`) — resolve o problema de colunas novas
- ACID transactions — nao corrompe dados em caso de falha no meio da escrita
- Time travel — rollback se uma transformacao gerar dados incorretos
- Audit history — rastreabilidade completa de quem mudou o que e quando

---

## 8. Plano de Implementacao

### Fase 1: Infra AWS + Databricks + Fundacao (~3h)

**Objetivo**: Setup completo do ambiente cloud e pipeline Bronze funcional.

| Etapa | Descricao | Dependencia |
|-------|-----------|-------------|
| 1.1 | Setup projeto local (pyproject.toml, estrutura dirs, config) | Nenhuma |
| 1.2 | Configurar AWS: criar S3 bucket com pastas bronze/silver/gold | Nenhuma |
| 1.3 | Configurar Databricks Workspace na AWS | 1.2 |
| 1.4 | Configurar Unity Catalog: criar catalog + schemas (bronze, silver, gold) | 1.3 |
| 1.5 | Contratos de schema na lib/ (required columns, constraints) | 1.1 |
| 1.6 | Notebook Bronze: ingestao do Parquet do S3 + validacao com schema evolution | 1.4 |
| 1.7 | Upload manual do Parquet para S3 (via console AWS ou CLI, unica vez para dev) | 1.2 |
| 1.8 | Registrar tabela Bronze no Unity Catalog | 1.6 |

**Entregavel**: Dados Bronze no S3, tabela registrada no Unity Catalog, notebook Bronze funcional.

### Fase 2: Silver Layer — 3 Tasks Desacopladas (~4h)

| Etapa | Descricao | Dependencia |
|-------|-----------|-------------|
| 2.1 | Task 2a: dedup sent+delivered + normalizacao nomes + parse metadata → `messages_clean` | 1.8 |
| 2.2 | UDFs PySpark na lib/: extratores CPF, email, telefone, placa, CEP | 1.1 |
| 2.3 | Mascaramento + redaction do message_body (lib/masking/) | 2.2 |
| 2.4 | Task 2b: extracao entidades + mascaramento + redaction → `leads_profile` | 2.1, 2.3 |
| 2.5 | Task 2c: enriquecimento por conversa → `conversations_enriched` | 2.1 |
| 2.6 | Registrar tabelas Silver no Unity Catalog com mergeSchema | 2.4, 2.5 |

**Entregavel**: Silver desacoplada em 3 tasks. Task 2b e 2c podem rodar em paralelo. Falha em uma nao perde trabalho das outras.

### Fase 3: Gold Layer (~4h)

| Etapa | Descricao | Dependencia |
|-------|-----------|-------------|
| 3.1 | Gold funil de conversao | 2.6 |
| 3.2 | Gold desempenho de agentes (scoring + ranking) | 2.6 |
| 3.3 | Gold sentimento (heuristica pt-BR) | 2.6 |
| 3.4 | Gold email providers + device analysis | 2.6 |
| 3.5 | Gold analise temporal (horarios, dias, response_time) | 2.6 |
| 3.6 | Gold inteligencia competitiva (concorrentes + precos) | 2.6 |
| 3.7 | Gold lead scoring | 3.3 |
| 3.8 | Gold personas/segmentacao | 3.7 |
| 3.9 | Gold churn/reengajamento | 2.6 |
| 3.10 | Gold complexidade da negociacao | 2.6 |
| 3.11 | Gold first contact resolution | 2.6 |

**Entregavel**: 12 tabelas Gold como Delta Tables. Insights acionaveis para negocio.

### Fase 4: Agente (pre+post) + Workflow + Observabilidade (~3h)

| Etapa | Descricao | Dependencia |
|-------|-----------|-------------|
| 4.1 | Notebook `agent_pre.py`: pre-check, fingerprint S3, versoes Delta, task values | Fase 1 |
| 4.2 | Notebook `agent_post.py`: post-check, recovery, rollback, notificacoes email | 4.1 |
| 4.3 | Delta Tables: `pipeline.state`, `pipeline.metrics`, `pipeline.notifications` | 4.1 |
| 4.4 | Notebook `validation/checks.py`: quality checks Bronze->Silver->Gold | Fase 3 |
| 4.5 | Criar Workflow completo (Tasks 0-5, max_concurrent_runs=1) | 4.1-4.4 |
| 4.6 | Configurar cron diario + retries por task | 4.5 |
| 4.7 | Metricas por task (log_metrics em cada notebook) | 4.3 |
| 4.8 | Dashboard Databricks SQL (status, metricas, notificacoes) | 4.7 |
| 4.9 | Databricks SQL Alerts (falhas consecutivas, dias sem sucesso) | 4.8 |

**Entregavel**: Pipeline autonomo com monitoramento visual, notificacoes por email, e auto-recovery.

### Fase 5: Diferenciais + Polimento (~2h)

| Etapa | Descricao | Dependencia |
|-------|-----------|-------------|
| 5.1 | Upgrade sentimento com pysentimiento (UDF Spark) | 3.3 |
| 5.2 | Gold predicao de outcome (ML simples) | 3.7 |
| 5.3 | Gold campaign ROI + analise geografica | 3.1 |
| 5.4 | Testes unitarios dos extratores (lib/) | Fase 2 |
| 5.5 | README.md com instrucoes de setup (Databricks + S3) | Fase 4 |
| 5.6 | CI basico: GitHub Actions rodando pytest nos extratores | 5.4 |

### Diagrama de Dependencias

```
Fase 1 (Infra Databricks + Bronze)
  |
  +--> Fase 2 (Silver — 3 tasks desacopladas)
  |      |
  |      +--> Fase 3 (Gold — 12 tabelas)
  |             |
  |             +--> Fase 4 (Agente pre+post + Workflow + Observabilidade)
  |             |      |
  |             |      +--> Fase 5 (Diferenciais + Polish + CI)
  |             |
  |             +--> Fase 5.1-5.3 (ML extras, em paralelo)
  |
  +--> Fase 4.1-4.2 (Agente pode comecar em paralelo com Silver/Gold)
```

---

## 9. Riscos e Mitigacoes

### 9.1 Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| **Regex de extracao com falsos positivos** | Alta | Medio | Validacao pos-extracao (digitos verificadores do CPF, formato de placa valido). Testes com amostras reais. Log de matches para auditoria. |
| **Transcricoes de audio com erros de speech-to-text** | Alta | Baixo | Tratar audio como "baixa confianca". Nao confiar em CPF/placa extraidos de audio sem validacao cruzada com mensagens de texto do mesmo lead. |
| **Dados de texto em formato inesperado** | Media | Medio | Extratores devem usar try/except por mensagem. Falha em uma mensagem nao afeta as demais. Log de erros para melhoria continua dos regex. |
| **Performance com datasets maiores** | Baixa (dados atuais sao pequenos) | Alto | PySpark no Databricks escala horizontalmente. Para volumes 10-100x maiores, basta aumentar o cluster. Sem mudanca de codigo. |
| **Sentimento heuristico impreciso** | Media | Baixo | A heuristica e um MVP. O pipeline e extensivel -- trocar para modelo ML requer apenas alterar `gold/sentiment.py`. Validar contra outcomes reais. |
| **Conflito de dependencias Python** | Baixa | Alto | Usar `uv` com lockfile exato. Pinnar versoes em pyproject.toml. Virtual environment isolado. |

### 9.2 Riscos de Negocio

| Risco | Mitigacao |
|-------|-----------|
| **Dados sensiveis expostos no GitHub** | `.gitignore` rigoroso: `data/`, `.env`, `*.parquet`. Dados de teste em `tests/fixtures/` sao sinteticos. Mascaramento ocorre antes de qualquer persistencia em Silver. |
| **Pipeline nao e "persistente o suficiente"** | Databricks Workflow roda como job agendado na cloud. Agente dentro do Databricks. Persistencia nativa. Nada depende de processo local. |
| **Custos AWS/Databricks** | Usar cluster single-node ou serverless para manter custo minimo. Free trial do Databricks cobre o necessario. S3 standard para storage barato. |
| **Credenciais expostas no GitHub** | Toda autenticacao via env vars e `.env` (gitignored). Databricks usa service principal ou PAT token. AWS usa IAM roles ou access keys em env. |
| **Gold layer nao demonstra criatividade** | 9 tabelas Gold propostas, muito alem das 4 sugeridas. Inclui ML (lead scoring, predicao), NLP (sentimento), e inteligencia competitiva. |
| **Auto-correcao do agente e superficial** | Implementar 3 niveis: (1) retry automatico, (2) rollback para ultimo estado valido, (3) alerta com diagnostico para intervencao humana. Logar toda decisao de correcao. |

### 9.3 Riscos de Prazo

| Risco | Mitigacao |
|-------|-----------|
| **Tempo insuficiente para tudo** | Fases priorizadas. Fase 1+2+3 entregam um projeto completo e funcional. Fases 4-5 sao bonus. Cada fase e independentemente demonstravel. |
| **Over-engineering** | Manter foco em: funciona > e bonito. Heuristica de sentimento antes de ML. Agente simples antes de features avancadas. |
| **Debug demorado em regex** | Preparar suite de testes dos extratores primeiro (TDD). Usar exemplos reais do dataset. Ter fallback para "nao encontrado" em vez de falha. |

### 9.4 Decisoes Arquiteturais Registradas (ADRs)

**ADR-001: Tudo dentro do Databricks (sem processo local em producao)**
- Decisao: Pipeline + agente rodam inteiramente no Databricks sobre AWS. Nada local em producao.
- Contexto: Dados chegam no S3 externamente. Workflow dispara diariamente. Agente e uma task do Workflow.
- Consequencia: Zero dependencia de maquina local. Infra 100% cloud. Deploy via Databricks Repos (sync com GitHub).

**ADR-002: PySpark como engine no Databricks, Polars para dev local**
- Decisao: PySpark e o engine de processamento dentro do Databricks. Polars opcionalmente para testes locais rapidos.
- Contexto: PySpark e nativo do Databricks, sem fricao. Delta Lake integrado. Escala automaticamente.
- Consequencia: Codigo de transformacao em PySpark. Desenvolvimento local pode usar Polars para prototipagem.

**ADR-003: Delta Lake com schema evolution sobre Parquet puro**
- Decisao: Todas as camadas usam Delta Tables com `mergeSchema=true`
- Contexto: Requisito de escala horizontal (colunas novas). Delta oferece ACID, time travel, audit.
- Consequencia: Colunas novas sao aceitas automaticamente. Rollback possivel. Overhead minimo sobre Parquet.

**ADR-004: Heuristica antes de ML para sentimento**
- Decisao: Implementar sentimento por regras primeiro, ML como upgrade
- Contexto: Tempo limitado, ML requer tuning e validacao
- Consequencia: Entrega mais rapida, resultado "good enough", facilmente substituivel

**ADR-005: Mascaramento parcial com hash deterministico**
- Decisao: Mascarar mantendo formato + hash HMAC para joins
- Contexto: Requisito de preservar dimensoes + possibilidade de correlacao futura
- Consequencia: Dados uteis analiticamente, irreversiveis sem a chave HMAC, compliant com LGPD

**ADR-006: Agente dividido em Task 0 (pre) e Task 5 (post)**
- Decisao: Agente e dois notebooks — `agent_pre.py` (Task 0) e `agent_post.py` (Task 5, run_if: ALL_DONE).
- Contexto: O agente precisa executar logica ANTES (pre-check) e APOS (recovery, notificacao) as tasks de dados. Uma unica Task 0 nao permite pos-execucao.
- Consequencia: Task 5 roda sempre (mesmo se tasks falharam), garante email em TODOS os cenarios, recovery com rollback Delta.

**ADR-007: Silver desacoplada em 3 tasks**
- Decisao: Silver e 3 tasks independentes (dedup_clean, entities_mask, enrichment) em vez de 1 monolitica.
- Contexto: Se extracao de entidades falhar, deduplicacao ja feita nao e perdida. Task 2b e 2c podem rodar em paralelo.
- Consequencia: Retry mais granular, menos retrabalho em caso de falha, ligeiramente mais complexo de configurar no Workflow.

**ADR-008: Parquet cru separado do Bronze Delta**
- Decisao: Parquet cru no S3 `/bronze/` e a fonte de dados. Bronze Delta Table no Unity Catalog e o dado registrado.
- Contexto: Preserva o arquivo original intocado. Permite schema evolution no Bronze Delta sem alterar a fonte.
- Consequencia: Clareza conceitual. Auditoria do dado original. Delta features (time travel, audit) desde a primeira camada.

---

## Apendice A: Estimativas de Volume e Performance

| Metrica | Valor |
|---------|-------|
| Linhas Bronze | 153.228 |
| Linhas Silver estimadas (pos-dedup) | ~142.000-145.000 |
| Leads unicos | ~15.000 |
| Tamanho Bronze Parquet | ~9 MB |
| Tamanho Silver estimado | ~12-15 MB (mais colunas) |
| Tamanho Gold estimado (todas tabelas) | ~2-5 MB (agregados) |
| Tempo de processamento Bronze->Gold (PySpark single-node) | ~30-90 segundos |
| Tempo com sentimento ML | ~2-5 minutos |
| Uso de memoria estimado | ~200-500 MB |

## Apendice B: Regex Patterns Consolidados

```python
# Todos os patterns validados contra exemplos reais do dataset

PATTERNS = {
    "cpf": r'\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b',
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "phone": r'(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)(?:9\s?)?\d{4}[\s-]?\d{4}',
    "plate_mercosul": r'\b([A-Z]{3}\d[A-Z]\d{2})\b',
    "plate_old": r'\b([A-Z]{3}-?\d{4})\b',
    "cep": r'\b(\d{5}-?\d{3})\b',
    "price_brl": r'R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)',
    "year": r'\b(19[89]\d|20[012]\d)\b',
}
```

## Apendice C: Criterios de Validacao por Camada

**Bronze -> Silver**:
- Row count Silver <= Row count Bronze (dedup remove linhas)
- Row count Silver >= Row count Bronze * 0.85 (nao perder mais de 15%)
- Todos os conversation_id de Bronze presentes em Silver
- Nenhum CPF/email/telefone em texto claro em Silver (mascaramento validado)

**Silver -> Gold**:
- Cada tabela Gold tem >= 1 linha
- Soma de outcomes no funil = total de conversas unicas
- Scores de lead scoring entre 0 e 100
- Sentimento entre -1.0 e 1.0
- Nenhum agent_id desconhecido nas metricas de agente