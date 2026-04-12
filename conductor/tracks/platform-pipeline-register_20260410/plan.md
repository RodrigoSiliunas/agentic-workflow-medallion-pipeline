# Plan: Pipeline Registration Post-Deploy

## Tasks

- [x] `deployment_saga.py` importa `Pipeline` e cria registro apos success
- [x] Preenche `deployment.pipeline_id` com o novo UUID
- [x] Frontend `DeployProgress.openPipelineChat` recarrega store antes de navegar
- [x] Smoke E2E (deploy → pipeline listado)
