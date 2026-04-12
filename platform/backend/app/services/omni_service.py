"""Servico de integracao com Omni — gerencia canais externos."""


import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Mapeamento do channel simplificado (frontend) → channel Omni
_CHANNEL_MAP = {
    "whatsapp": "whatsapp-baileys",
    "discord": "discord",
    "telegram": "telegram",
    "slack": "slack",
}


class OmniService:
    """Client para Omni API. Gerencia instancias de canal."""

    def __init__(self):
        self.base_url = settings.OMNI_API_URL
        self.api_key = settings.OMNI_API_KEY

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key, "Content-Type": "application/json"}

    @staticmethod
    def _unwrap(body: dict) -> dict:
        """Omni retorna respostas wrappadas em {"data": {...}}."""
        return body.get("data", body)

    async def health_check(self) -> bool:
        """Verifica se Omni esta respondendo."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.base_url}/health", headers=self._headers()
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def create_instance(
        self, name: str, channel: str, company_slug: str
    ) -> dict:
        """Cria instancia de canal no Omni.

        Name convention: {company_slug}_{channel} (ex: acme_whatsapp)
        """
        omni_channel = _CHANNEL_MAP.get(channel, channel)
        instance_name = f"{company_slug}_{channel}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
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
        """Obtem detalhes de uma instancia no Omni."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/instances/{instance_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return self._unwrap(resp.json())

    async def connect_instance(
        self, instance_id: str, token: str | None = None
    ) -> dict:
        """Conecta instancia (passa token para Discord/Telegram)."""
        payload = {}
        if token:
            payload["token"] = token

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/instances/{instance_id}/connect",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return self._unwrap(resp.json())

    async def disconnect_instance(self, instance_id: str) -> dict:
        """Desconecta instancia."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/instances/{instance_id}/disconnect",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return self._unwrap(resp.json())

    async def get_qr_code(self, instance_id: str) -> dict:
        """Obtem QR code para WhatsApp pairing."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/instances/{instance_id}/qr",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return self._unwrap(resp.json())

    async def configure_webhook_provider(
        self, backend_webhook_url: str
    ) -> dict:
        """Configura webhook provider apontando para nosso backend."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/providers",
                json={
                    "name": "namastex-platform",
                    "schema": "webhook",
                    "baseUrl": backend_webhook_url,
                },
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def send_message(
        self, instance_id: str, to: str, text: str
    ) -> dict:
        """Envia mensagem via Omni para um canal."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/messages/send",
                json={
                    "instanceId": instance_id,
                    "to": to,
                    "text": text,
                },
                headers=self._headers(),
            )
            resp.raise_for_status()
            return self._unwrap(resp.json())

    async def list_instances(self) -> list[dict]:
        """Lista todas as instancias."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/instances", headers=self._headers()
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("items", body.get("data", []))
