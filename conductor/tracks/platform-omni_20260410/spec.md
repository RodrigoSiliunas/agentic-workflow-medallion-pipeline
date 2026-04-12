# Specification: Platform — Omni Multi-channel Integration

**Track ID:** platform-omni_20260410
**Type:** Feature
**Created:** 2026-04-10
**Status:** Draft

## Summary

Completar a integracao do Omni (gateway multi-canal: WhatsApp + Discord + Telegram) com a plataforma Namastex. O backend ja possui `OmniService` completo (create/connect/disconnect/qr/send_message), webhook receiver com HMAC + slash commands funcionais, e models de `ChannelIdentity`/`ActiveSession`. O que falta e o control plane: um model `OmniInstance` pra persistir metadata, router `/api/v1/channels` com CRUD, e UI no frontend pra criar/listar/desconectar instancias e escanear QR code do WhatsApp.

## User Story

Como Rodrigo (admin), quero entrar na area "Channels" da plataforma e: **(1)** ver todas as instancias Omni conectadas (WhatsApp, Discord, Telegram) com status; **(2)** criar uma nova instancia de WhatsApp, clicar em "Pair" e ver um QR code pra escanear no meu celular; **(3)** conectar um bot Discord colando o token; **(4)** desconectar uma instancia obsoleta com 1 click. Depois disso, quero que qualquer mensagem que chegar num dos canais seja roteada automaticamente para o thread ativo no chat — o backend ja sabe fazer isso via webhook.

## Acceptance Criteria

### Backend — Model + Schemas

- [ ] `app/models/channel.py` ganha nova classe `OmniInstance` (ou arquivo novo `omni_instance.py`)
  - `id` UUID, `company_id` FK, `omni_instance_id` (string do Omni), `name`, `channel` (whatsapp/discord/telegram), `state` (connecting/connected/disconnected/failed), `last_sync_at`, timestamps
- [ ] `app/models/__init__.py` exporta o novo model
- [ ] Alembic migration `0006_add_omni_instances`
- [ ] `app/schemas/channel.py` com `OmniInstanceResponse`, `CreateChannelRequest`, `QRCodeResponse`

### Backend — Router `/api/v1/channels`

- [ ] `GET /channels` — lista instancias da empresa
- [ ] `POST /channels` — cria instancia:
  - Chama `OmniService.create_instance(name, channel, company_slug)`
  - Persiste OmniInstance com `omni_instance_id` retornado
  - Retorna OmniInstanceResponse
- [ ] `GET /channels/{id}/qr` — busca QR code via `OmniService.get_qr_code()` (so pra WhatsApp)
- [ ] `POST /channels/{id}/connect` — passa token Discord/Telegram via `OmniService.connect_instance()`
- [ ] `DELETE /channels/{id}` — chama `OmniService.disconnect_instance()` + marca state=disconnected (soft delete)
- [ ] Todas as rotas sao protegidas por JWT + permissao `manage_pipelines` ou superior
- [ ] Fallback gracioso: se Omni indisponivel, persiste OmniInstance com state=failed e retorna 503 com mensagem clara

### Backend — Tests

- [ ] `tests/unit/test_omni_instance_model.py` — shape do model
- [ ] `tests/unit/test_channels_schemas.py` — Pydantic validation
- [ ] (opcional) Integration test do router com OmniService mockado

### Frontend — Types + Store + Composables

- [ ] `types/channel.ts` — `OmniInstance`, `OmniInstanceState`, `ChannelKind`
- [ ] `composables/useChannelsApi.ts` — list, create, connect, disconnect, getQrCode
- [ ] `stores/channels.ts` — Pinia store dual-source (mocks em mockMode, API real fora)

### Frontend — Pages + Organisms

- [ ] `pages/channels/index.vue` — grid de instancias + botao "Nova instancia"
- [ ] `organisms/ChannelCard.vue` (molecule) — card com icone do canal, status, botoes action
- [ ] `organisms/NewChannelModal.vue` — modal que escolhe WhatsApp/Discord/Telegram + nome + inicia criacao
- [ ] `organisms/QrPairingModal.vue` — modal que mostra QR code em tamanho grande + polling de status
- [ ] Todos os componentes usam tokens Namastex

### Frontend — Sidebar Integration

- [ ] `ModuleSwitcher.vue` ganha 4a entrada "Channels" com icone `phone` (ou similar)
- [ ] `SidebarNav.vue` ganha mode `channels` com lista de instancias ativas
- [ ] `settings.vue` — botao "Conectar WhatsApp" atualmente desabilitado vira um link `/channels`

### Mocks para dev offline

- [ ] 3 instancias mockadas: 1 WhatsApp conectada, 1 Discord conectada, 1 Telegram em "connecting"

## Dependencies

- **platform-backend-wire_20260410** — padrao de routers, stores dual-source e AUTO_SEED ja estabelecido (COMPLETE)
- Backend ja tem `OmniService` completo + webhook receiver

## Out of Scope

- QR scanner nativo (apenas exibicao do QR — usuario escaneia com o celular)
- Multi-WhatsApp por empresa (so 1 por enquanto — validado no POST)
- Historico de mensagens cross-channel (o handler ja salva no thread via ActiveSession, nao precisamos de UI especifica)
- Billing por canal
- Auto-reconnect quando Omni cai
- Broadcast de pipeline alerts para canais (`/pipeline` webhook stub fica para track futura)

## Technical Notes

### State machine do OmniInstance

```
connecting → connected → disconnected
    ↓            ↓
  failed      failed
```

- `connecting`: Omni aceitou a criacao mas ainda nao terminou (WhatsApp aguardando QR scan)
- `connected`: instancia ativa, recebendo/enviando mensagens
- `disconnected`: usuario clicou delete, ou Omni desconectou
- `failed`: erro na criacao ou no Omni

### QR code polling

No frontend, quando abre o `QrPairingModal`, ele faz polling a cada 3s no `GET /channels/{id}/qr` (se o endpoint retornar `status: "connected"`, fecha o modal e atualiza a lista).

### Fallback quando Omni indisponivel

Tanto backend quanto frontend precisam lidar com Omni offline graciosamente:
- Backend: se `create_instance` lanca exception, loga + retorna HTTP 503 com "Omni gateway indisponivel"
- Frontend: mostra banner de warning no topo da pagina se `Omni health check` falhar ao carregar

---

_Generated by Conductor._
