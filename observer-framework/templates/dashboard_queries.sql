-- ============================================================
-- Dashboard Databricks SQL: Observer Agent
-- Observabilidade do agente autonomo que diagnostica e corrige
-- falhas do pipeline ETL. Criar cada query como um painel no
-- Dashboard do Databricks SQL.
--
-- Tabela: medallion.observer.diagnostics
-- Populada automaticamente pelo notebook observer/collect_and_fix.py
-- ============================================================

-- ============================================================
-- PAINEL 1: Diagnosticos por dia (ultimos 30 dias)
-- Mostra a atividade do Observer ao longo do tempo
-- ============================================================
SELECT
    DATE(timestamp) AS dia,
    status,
    COUNT(*) AS diagnosticos
FROM medallion.observer.diagnostics
WHERE timestamp >= DATE_ADD(CURRENT_DATE(), -30)
GROUP BY DATE(timestamp), status
ORDER BY dia DESC, status;

-- ============================================================
-- PAINEL 2: Custo estimado por provider (ultimos 30 dias)
-- Acompanha gasto com LLMs
-- ============================================================
SELECT
    provider,
    model,
    COUNT(*) AS chamadas,
    SUM(input_tokens) AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens,
    ROUND(SUM(estimated_cost_usd), 4) AS custo_total_usd
FROM medallion.observer.diagnostics
WHERE timestamp >= DATE_ADD(CURRENT_DATE(), -30)
  AND provider IS NOT NULL
  AND provider <> ''
GROUP BY provider, model
ORDER BY custo_total_usd DESC;

-- ============================================================
-- PAINEL 3: Custo acumulado ao longo do tempo
-- Line chart da evolucao de gasto
-- ============================================================
SELECT
    DATE(timestamp) AS dia,
    ROUND(SUM(estimated_cost_usd), 4) AS custo_dia_usd,
    ROUND(
        SUM(SUM(estimated_cost_usd)) OVER (ORDER BY DATE(timestamp)),
        4
    ) AS custo_acumulado_usd
FROM medallion.observer.diagnostics
WHERE timestamp >= DATE_ADD(CURRENT_DATE(), -60)
GROUP BY DATE(timestamp)
ORDER BY dia;

-- ============================================================
-- PAINEL 4: Confianca media por task
-- Identifica tasks onde o LLM tem baixa confianca
-- ============================================================
SELECT
    failed_task,
    COUNT(*) AS total_diagnosticos,
    ROUND(AVG(confidence), 3) AS confianca_media,
    ROUND(MIN(confidence), 3) AS confianca_minima,
    ROUND(MAX(confidence), 3) AS confianca_maxima
FROM medallion.observer.diagnostics
WHERE confidence > 0
GROUP BY failed_task
ORDER BY total_diagnosticos DESC;

-- ============================================================
-- PAINEL 5: Top 10 erros mais frequentes
-- Permite priorizar correcoes recorrentes (candidatos para dedup)
-- ============================================================
SELECT
    error_hash,
    SUBSTRING(error_message, 1, 120) AS erro_resumo,
    COUNT(*) AS ocorrencias,
    COUNT(DISTINCT run_id) AS runs_distintos,
    MIN(timestamp) AS primeira_ocorrencia,
    MAX(timestamp) AS ultima_ocorrencia
FROM medallion.observer.diagnostics
WHERE error_hash IS NOT NULL
GROUP BY error_hash, SUBSTRING(error_message, 1, 120)
ORDER BY ocorrencias DESC
LIMIT 10;

-- ============================================================
-- PAINEL 6: Taxa de sucesso por status
-- Quantos diagnosticos viraram PR, falharam no LLM, etc.
-- ============================================================
SELECT
    status,
    COUNT(*) AS total,
    ROUND(
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (),
        2
    ) AS percentual
FROM medallion.observer.diagnostics
GROUP BY status
ORDER BY total DESC;

-- ============================================================
-- PAINEL 7: Tempo medio de diagnostico por provider
-- Compara latencia entre LLMs
-- ============================================================
SELECT
    provider,
    model,
    ROUND(AVG(duration_seconds), 2) AS tempo_medio_s,
    ROUND(MAX(duration_seconds), 2) AS tempo_max_s,
    COUNT(*) AS execucoes
FROM medallion.observer.diagnostics
WHERE duration_seconds > 0
GROUP BY provider, model
ORDER BY tempo_medio_s;

-- ============================================================
-- PAINEL 8: PRs criados recentemente
-- Lista auditavel dos PRs que o Observer abriu
-- ============================================================
SELECT
    timestamp,
    job_name,
    failed_task,
    ROUND(confidence, 2) AS confianca,
    pr_number,
    pr_url,
    pr_status,
    provider || '/' || model AS llm
FROM medallion.observer.diagnostics
WHERE pr_url IS NOT NULL AND pr_url <> ''
ORDER BY timestamp DESC
LIMIT 20;

-- ============================================================
-- PAINEL 9: Taxa de aceitacao dos fixes (feedback loop)
-- Mostra eficacia do Observer: quantos PRs foram mergeados
-- ============================================================
SELECT
    COALESCE(pr_status, 'pending') AS pr_status,
    feedback,
    COUNT(*) AS total,
    ROUND(
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (),
        2
    ) AS percentual
FROM medallion.observer.diagnostics
WHERE status = 'success'  -- so PRs que realmente foram criados
GROUP BY COALESCE(pr_status, 'pending'), feedback
ORDER BY total DESC;

-- ============================================================
-- PAINEL 10: Tempo medio de resolucao (merged vs closed)
-- Quanto tempo entre o Observer criar o PR e ser resolvido
-- ============================================================
SELECT
    pr_status,
    COUNT(*) AS prs_resolvidos,
    ROUND(AVG(resolution_time_hours), 2) AS tempo_medio_h,
    ROUND(MIN(resolution_time_hours), 2) AS tempo_min_h,
    ROUND(MAX(resolution_time_hours), 2) AS tempo_max_h
FROM medallion.observer.diagnostics
WHERE pr_status IN ('merged', 'closed')
  AND resolution_time_hours IS NOT NULL
GROUP BY pr_status;

-- ============================================================
-- PAINEL 11: Eficacia por provider/modelo
-- Qual LLM gera fixes mais aceitos
-- ============================================================
SELECT
    provider,
    model,
    COUNT(*) AS prs_criados,
    SUM(CASE WHEN feedback = 'fix_accepted' THEN 1 ELSE 0 END) AS aceitos,
    SUM(CASE WHEN feedback = 'fix_rejected' THEN 1 ELSE 0 END) AS rejeitados,
    ROUND(
        SUM(CASE WHEN feedback = 'fix_accepted' THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(*), 0),
        2
    ) AS taxa_aceitacao_pct
FROM medallion.observer.diagnostics
WHERE status = 'success' AND pr_number > 0
GROUP BY provider, model
ORDER BY taxa_aceitacao_pct DESC NULLS LAST;

-- ============================================================
-- ALERTS (criar via Databricks SQL Alerts)
-- ============================================================

-- ALERT 1: Custo do Observer nas ultimas 24h excedeu $5
SELECT ROUND(COALESCE(SUM(estimated_cost_usd), 0), 4) AS custo_24h
FROM medallion.observer.diagnostics
WHERE timestamp >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS;
-- Condicao: custo_24h > 5 -> alerta

-- ALERT 2: Taxa de falha do LLM nas ultimas 24h > 10%
WITH stats AS (
    SELECT
        SUM(CASE WHEN status = 'llm_failed' THEN 1 ELSE 0 END) AS falhas,
        COUNT(*) AS total
    FROM medallion.observer.diagnostics
    WHERE timestamp >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
)
SELECT
    CASE WHEN total > 0 THEN ROUND(falhas * 100.0 / total, 2) ELSE 0 END
        AS taxa_falha_pct
FROM stats;
-- Condicao: taxa_falha_pct > 10 -> alerta

-- ALERT 3: Mesmo erro (error_hash) repetido > 3 vezes nas ultimas 6h
-- Indica que os PRs nao estao sendo mergeados ou nao resolvem o problema
SELECT error_hash, COUNT(*) AS repeticoes
FROM medallion.observer.diagnostics
WHERE timestamp >= CURRENT_TIMESTAMP() - INTERVAL 6 HOURS
GROUP BY error_hash
HAVING COUNT(*) > 3
ORDER BY repeticoes DESC;
-- Condicao: linhas retornadas > 0 -> alerta
