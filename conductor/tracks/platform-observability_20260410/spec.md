# Specification: Observability Metrics + Widget

**Track ID:** platform-observability_20260410
**Status:** Complete

## Summary

Endpoint `/api/v1/observability/metrics` agrega dados reais da empresa (deployments, pipelines, channels) + metricas mockadas do Observer Agent. Widget `ObservabilityWidget` exibe 4 MetricCard no empty state do `/chat`.

## Entrega

### Backend

- `app/schemas/observability.py` com `ObservabilityMetrics`, `DeploymentBreakdown`, `PipelineMetrics`, `ChannelMetrics`, `ObserverMetrics`
- `app/api/routes/observability.py`:
  - `GET /metrics` agrega por `company_id` via SQL groupby
  - Observer metrics sao mockadas (futuro: real via `medallion.observer.diagnostics`)
- Router registrado em `main.py`

### Frontend

- `types/observability.ts` + `composables/useObservabilityApi.ts` (com fallback mock)
- `molecules/MetricCard.vue` — card reutilizavel label/value/icon/hint
- `organisms/ObservabilityWidget.vue` — 4 cards grid (Pipelines, Deploys, Canais, Observer)
- Injetado em `pages/chat/index.vue` acima das suggestion cards

## Smoke E2E validado

```json
{
  "pipelines": {"total": 2, "with_databricks_job": 0},
  "deployments": {"total": 1, "success": 1, "avg_duration_seconds": 20.238},
  "channels": {"total": 0, "by_channel": {}, "connected": 0},
  "observer": {"total_diagnostics": 23, "prs_created": 19, "estimated_cost_usd": 4.82}
}
```

## Out of scope

- Observer metrics reais (requer Databricks SQL connector — follow-up)
- Historico temporal (daily breakdown, etc.)
- Filtros por periodo
