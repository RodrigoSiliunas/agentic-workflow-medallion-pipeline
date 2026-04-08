-- ============================================================
-- Dashboard Databricks SQL: Pipeline Medallion
-- Criar cada query como um painel no Dashboard
-- ============================================================

-- PAINEL 1: Status do ultimo run
SELECT
    run_at,
    status,
    consecutive_failures,
    last_bronze_hash
FROM medallion.pipeline.state
ORDER BY run_at DESC
LIMIT 1;

-- PAINEL 2: Historico de execucoes (ultimos 30 dias)
SELECT
    DATE(run_at) as dia,
    status,
    COUNT(*) as runs
FROM medallion.pipeline.state
WHERE run_at >= DATE_ADD(CURRENT_DATE(), -30)
GROUP BY DATE(run_at), status
ORDER BY dia DESC;

-- PAINEL 3: Metricas por task (ultimo run)
SELECT
    task,
    rows_input,
    rows_output,
    rows_error,
    duration_sec
FROM medallion.pipeline.metrics
WHERE run_id = (SELECT run_id FROM medallion.pipeline.metrics ORDER BY timestamp DESC LIMIT 1)
ORDER BY task;

-- PAINEL 4: Taxa de erro de extracao
SELECT
    task,
    AVG(CASE WHEN rows_input > 0 THEN rows_error * 100.0 / rows_input ELSE 0 END) as avg_error_rate_pct
FROM medallion.pipeline.metrics
WHERE task LIKE 'silver%'
GROUP BY task;

-- PAINEL 5: Tempo medio por etapa
SELECT
    task,
    AVG(duration_sec) as avg_duration_sec,
    MAX(duration_sec) as max_duration_sec,
    COUNT(*) as total_runs
FROM medallion.pipeline.metrics
GROUP BY task
ORDER BY avg_duration_sec DESC;

-- PAINEL 6: Notificacoes recentes
SELECT
    timestamp,
    level,
    subject,
    run_id
FROM medallion.pipeline.notifications
ORDER BY timestamp DESC
LIMIT 20;

-- ============================================================
-- ALERTS (criar via Databricks SQL Alerts)
-- ============================================================

-- ALERT 1: Falhas consecutivas > 0
SELECT consecutive_failures
FROM medallion.pipeline.state
ORDER BY run_at DESC
LIMIT 1;
-- Condicao: resultado > 0 -> disparar alerta

-- ALERT 2: Erros de extracao hoje
SELECT COUNT(*) as errors_today
FROM medallion.pipeline.metrics
WHERE rows_error > 0
  AND DATE(timestamp) = CURRENT_DATE();
-- Condicao: resultado > 0 -> disparar alerta

-- ALERT 3: Dias sem sucesso
SELECT DATEDIFF(CURRENT_DATE(), MAX(DATE(run_at))) as days_without_success
FROM medallion.pipeline.state
WHERE status = 'SUCCESS';
-- Condicao: resultado > 1 -> disparar alerta
