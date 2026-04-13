"""Servico de integracao com Omni — gerencia canais externos."""


import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Mapeamento do channel simplificado (frontend) → channel Omni
CHANNEL_MAP = {
    "whatsapp": "whatsapp-baileys",
    "discord": "discord",
    "telegram": "telegram",
    "slack": "slack",
}


class OmniService:
    """Client para Omni API. Usa httpx.AsyncClient compartilhado (connection pooling)."""

    _shared_client: httpx.AsyncClient | None = None

    def __init__(self):
        self.base_url = settings.OMNI_API_URL
        self.api_key = settings.OMNI_API_KEY

    @classmethod
    def _client(cls) -> httpx.AsyncClient:
        if cls._shared_client is None:
            cls._shared_client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return cls._shared_client

    @classmethod
    async def close(cls) -> None:
        if cls._shared_client:
            await cls._shared_client.aclose()
            cls._shared_client = None

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key, "Content-Type": "application/json"}

    @staticmethod
    def _unwrap(body: dict) -> dict:
        return body.get("data", body)

    async def health_check(self) -> bool:
        try:
            resp = await self._client().get(
                f"{self.base_url}/health", headers=self._headers()
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def create_instance(self, name: str, channel: str, company_slug: str) -> dict:
        omni_channel = CHANNEL_MAP.get(channel, channel)
        instance_name = f"{company_slug}_{channel}"
        resp = await self._client().post(
            f"{self.base_url}/instances",
            json={"name": instance_name, "channel": omni_channel},
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = self._unwrap(resp.json())
        logger.info(
            "Omni instance created",
            name=instance_name, channel=omni_channel, id=data.get("id"),
        )
        return data

    async def get_instance(self, instance_id: str) -> dict:
        resp = await self._client().get(
            f"{self.base_url}/instances/{instance_id}", headers=self._headers()
        )
        resp.raise_for_status()
        return self._unwrap(resp.json())

    async def connect_instance(self, instance_id: str, token: str | None = None) -> dict:
        payload: dict = {}
        if token:
            payload["options"] = {"token": token}
        resp = await self._client().post(
            f"{self.base_url}/instances/{instance_id}/connect",
            json=payload, headers=self._headers(),
        )
        resp.raise_for_status()
        return self._unwrap(resp.json())

    async def disconnect_instance(self, instance_id: str) -> dict:
        resp = await self._client().post(
            f"{self.base_url}/instances/{instance_id}/disconnect", headers=self._headers()
        )
        resp.raise_for_status()
        return self._unwrap(resp.json())

    async def get_qr_code(self, instance_id: str) -> dict:
        resp = await self._client().get(
            f"{self.base_url}/instances/{instance_id}/qr", headers=self._headers()
        )
        resp.raise_for_status()
        return self._unwrap(resp.json())

    async def configure_webhook_provider(self, backend_webhook_url: str) -> dict:
        resp = await self._client().post(
            f"{self.base_url}/providers",
            json={"name": "namastex-platform", "schema": "webhook", "baseUrl": backend_webhook_url},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def send_message(self, instance_id: str, to: str, text: str) -> dict:
        resp = await self._client().post(
            f"{self.base_url}/messages/send",
            json={"instanceId": instance_id, "to": to, "text": text},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return self._unwrap(resp.json())

    async def list_instances(self) -> list[dict]:
        resp = await self._client().get(
            f"{self.base_url}/instances", headers=self._headers()
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("items", body.get("data", []))

    async def get_new_events(self, since: str | None = None, limit: int = 20) -> list[dict]:
        params: dict = {
            "eventType": "message.received",
            "direction": "inbound",
            "limit": limit,
        }
        resp = await self._client().get(
            f"{self.base_url}/events", params=params, headers=self._headers()
        )
        resp.raise_for_status()
        body = resp.json()
        events = body.get("items", [])
        return [e for e in events if not e.get("processedAt")]

    async def mark_event_processed(self, event_id: str) -> None:
        resp = await self._client().patch(
            f"{self.base_url}/events/{event_id}",
            json={"status": "processed"}, headers=self._headers(),
        )
        if resp.status_code >= 400:
            logger.warning("Failed to mark event processed", event_id=event_id)
