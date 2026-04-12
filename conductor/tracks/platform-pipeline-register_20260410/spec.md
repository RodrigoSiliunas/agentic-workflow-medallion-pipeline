# Specification: Pipeline Registration Post-Deploy

**Track ID:** platform-pipeline-register_20260410
**Status:** Complete

## Summary

Apos saga de deploy completar com sucesso, o runner cria um `Pipeline` real no DB com metadata do template/deployment. Frontend entao pode listar esse pipeline no chat e o botao "Abrir chat" funciona de verdade.

## Entrega

### Backend

- `deployment_saga.run_saga()` apos marcar `status=success`:
  1. Cria `Pipeline(company_id, name=deployment.name, description="Deploy de {template_name}", config={template_slug, deployment_id, environment})`
  2. Flush + `deployment.pipeline_id = pipeline.id`
  3. Commit

### Frontend

- `DeployProgress.openPipelineChat()` agora async:
  - `await pipelinesStore.load(true)` pra incluir o novo pipeline
  - `setActive(pipelineId)` + `navigateTo('/chat')`

## Smoke E2E validado

```
POST /deployments → saga completa em 20s → pipeline_id populado ✓
GET /pipelines → default + hotmart-e2e (criado pela saga) ✓
```
