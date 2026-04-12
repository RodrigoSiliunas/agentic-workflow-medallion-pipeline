"""Factory que cria sessao boto3 com credenciais do StepContext."""

from __future__ import annotations

import boto3

from app.services.real_saga.base import DeploymentCredentials


def boto3_session(credentials: DeploymentCredentials) -> boto3.session.Session:
    """Cria uma sessao boto3 isolada com as credenciais do deploy.

    Nao usa a default chain (`~/.aws/credentials`) — as credenciais vem sempre
    do StepContext pra garantir multi-tenancy por empresa.
    """
    return boto3.session.Session(
        aws_access_key_id=credentials.require("aws_access_key_id"),
        aws_secret_access_key=credentials.require("aws_secret_access_key"),
        region_name=credentials.require("aws_region"),
    )
