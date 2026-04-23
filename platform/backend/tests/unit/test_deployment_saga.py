"""Unit tests para o deployment saga service (sem DB)."""

import asyncio

import pytest

from app.services.deployment_saga import (
    SAGA_BLUEPRINT,
    STEP_LOGS,
    _publish,
    subscribe,
    unsubscribe,
)


def test_saga_blueprint_structure():
    """Blueprint deve ter 16 etapas com id/name/description.

    Inclui os 10 originais + 6 novos do workspace setup from-scratch:
    network, workspace_credential, storage_configuration,
    workspace_provision, metastore_assign, cluster_provision.
    """
    assert len(SAGA_BLUEPRINT) == 16
    for step in SAGA_BLUEPRINT:
        assert "id" in step and step["id"]
        assert "name" in step and step["name"]
        assert "description" in step

    ids = [s["id"] for s in SAGA_BLUEPRINT]
    assert len(ids) == len(set(ids)), "step ids devem ser unicos"
    # Sanity check dos novos steps
    expected = {
        "network", "workspace_credential", "storage_configuration",
        "workspace_provision", "metastore_assign", "cluster_provision",
    }
    assert expected.issubset(set(ids))


def test_step_logs_cobrem_todos_os_steps():
    """Cada step do blueprint deve ter ao menos 1 log de exemplo."""
    blueprint_ids = {s["id"] for s in SAGA_BLUEPRINT}
    logs_ids = set(STEP_LOGS.keys())
    assert blueprint_ids == logs_ids
    for step_id, messages in STEP_LOGS.items():
        assert len(messages) >= 1, f"{step_id} sem logs de exemplo"


@pytest.mark.asyncio
async def test_subscribe_publish_unsubscribe_roundtrip():
    """subscribe -> publish -> consume -> unsubscribe funciona como pub/sub."""
    dep_id = "test-dep-1"
    queue = subscribe(dep_id)

    event = {"type": "log", "deployment_id": dep_id, "data": {"message": "hello"}}
    await _publish(dep_id, event)

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received == event

    unsubscribe(dep_id, queue)
    # Apos unsubscribe, publicar nao deve lancar nem preencher a queue
    await _publish(dep_id, {"type": "log", "deployment_id": dep_id, "data": {}})
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.1)


@pytest.mark.asyncio
async def test_multiple_subscribers_recebem_broadcast():
    """Multiplos subscribers do mesmo deployment recebem o mesmo evento."""
    dep_id = "test-dep-broadcast"
    q1 = subscribe(dep_id)
    q2 = subscribe(dep_id)

    event = {"type": "status_change", "deployment_id": dep_id, "data": {"status": "running"}}
    await _publish(dep_id, event)

    r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert r1 == event
    assert r2 == event

    unsubscribe(dep_id, q1)
    unsubscribe(dep_id, q2)


@pytest.mark.asyncio
async def test_publish_em_deployment_sem_subscribers_nao_explode():
    """Publicar em um deployment sem subscribers e no-op."""
    await _publish("unknown-dep", {"type": "log", "deployment_id": "unknown-dep", "data": {}})
