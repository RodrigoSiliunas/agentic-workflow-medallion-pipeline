"""Real saga runner — executa deploys de verdade via Terraform + Databricks SDK + boto3.

Modulo organizado em:

- `base.py`            — Protocols, dataclasses, tipos compartilhados.
- `terraform_runner.py` — Wrapper subprocess do binario `terraform` com streaming de logs.
- `databricks_client.py` — Factory que cria WorkspaceClient com as credenciais do contexto.
- `aws_client.py`      — Factory que cria sessao boto3 com as credenciais do contexto.
- `steps/`             — 1 arquivo por step da saga (validate/s3/iam/secrets/etc).
- `runner.py`          — RealSagaRunner que recebe o StepContext e despacha por step_id.

Ativacao: export `SAGA_RUNNER=real` no backend. O registry em `saga_runners.py`
vai resolver `RealSagaRunner` automaticamente.
"""

from app.services.real_saga.runner import RealSagaRunner

__all__ = ["RealSagaRunner"]
