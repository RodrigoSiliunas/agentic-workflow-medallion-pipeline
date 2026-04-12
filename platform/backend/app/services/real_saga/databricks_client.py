"""Factory que cria WorkspaceClient com credenciais do StepContext.

Nao usa caching — o databricks-sdk ja faz connection pooling internamente.
Criar um client novo por saga execution garante que tokens rotacionados
sao respeitados imediatamente e que tokens de uma empresa nao ficam em
memoria apos o deploy terminar.
"""

from __future__ import annotations

from databricks.sdk import WorkspaceClient

from app.services.real_saga.base import DeploymentCredentials


def workspace_client(credentials: DeploymentCredentials) -> WorkspaceClient:
    """Cria um WorkspaceClient autenticado com as credenciais do deploy."""
    host = credentials.require("databricks_host")
    token = credentials.require("databricks_token")
    return WorkspaceClient(host=host, token=token)
