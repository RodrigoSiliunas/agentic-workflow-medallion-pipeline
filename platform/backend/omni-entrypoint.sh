#!/bin/bash
set -e

# Garantir ownership do home do omni (volume pode vir com root)
chown -R omni:omni /home/omni

# Rodar omni install como user omni (instala config + inicia PM2 processes)
su-exec omni omni install \
  --port "$OMNI_PORT" \
  --api-key "$OMNI_API_KEY"

# Aguardar pgserve subir (PM2 inicia async)
echo "Aguardando pgserve..."
for i in $(seq 1 30); do
  if su-exec omni pg_isready -h 127.0.0.1 -p 8432 -q 2>/dev/null; then
    echo "pgserve pronto!"
    break
  fi
  sleep 1
done

# Setar API key conhecida no DB (Omni gera key aleatoria no install,
# precisamos sobrescrever com a key que o backend conhece)
HASH=$(echo -n "$OMNI_API_KEY" | sha256sum | awk '{print $1}')
PREFIX=$(echo "$OMNI_API_KEY" | sed 's/omni_sk_//' | cut -c1-8)
su-exec omni psql "postgresql://postgres:postgres@127.0.0.1:8432/omni" \
  -c "UPDATE api_keys SET key_hash = '$HASH', key_prefix = '$PREFIX' WHERE name = '__primary__';" \
  2>/dev/null && echo "API key atualizada: ${OMNI_API_KEY:0:20}..." || echo "WARN: Nao foi possivel atualizar API key"

# pm2-runtime como user omni (mantém container vivo e gerencia os processes)
exec su-exec omni pm2-runtime start all
