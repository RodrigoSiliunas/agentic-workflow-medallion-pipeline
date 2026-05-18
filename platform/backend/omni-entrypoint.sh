#!/bin/bash
set -e

# Garantir ownership do home do omni (volume pode vir com root)
chown -R omni:omni /home/omni

# Volume `flowertex_omnidata:/home/omni/.omni/data` so persiste pgdata.
# Tudo o resto em /home/omni/.omni/ e /home/omni/.pm2/ some no recreate:
# - .omni/config.json   (config do omni server)
# - .omni/nats-server   (binario nats baixado pelo omni install)
# - .omni/logs/         (paths absolutos referenciados no pm2 dump)
# - .pm2/dump.pm2       (processos pra pm2 resurrect)
#
# Estrategia: tar de tudo isso no proprio data volume (que persiste) e
# extracao antes do pm2 resurrect no restart.
BACKUP_DIR=/home/omni/.omni/data/.entrypoint_backup
STATE_TAR="$BACKUP_DIR/omni_state.tar.gz"
INITIALIZED="$BACKUP_DIR/.initialized"

su-exec omni mkdir -p "$BACKUP_DIR"

is_first_run=0
if [ ! -f "$INITIALIZED" ]; then
  is_first_run=1
fi

# Corruption recovery: .initialized existe (formato antigo so backup-ava
# config + pm2.dump) mas state.tar.gz nao foi salvo, entao nao temos como
# restaurar o nats-server binario que o pm2 resurrect precisa. Forca fresh
# install + limpa pgdata pra garantir consistencia (omni install supoe
# data dir vazio).
if [ "$is_first_run" = "0" ] && [ ! -f "$STATE_TAR" ]; then
  echo "Backup state.tar.gz ausente (entrypoint antigo) — limpando pgdata e reinstalando"
  su-exec omni rm -rf /home/omni/.omni/data/postgres
  su-exec omni rm -f "$BACKUP_DIR"/*.json "$BACKUP_DIR"/*.dump "$INITIALIZED"
  is_first_run=1
fi

# Legacy volume detection: postgres data existe (PG_VERSION) mas
# nao temos .initialized — volume foi criado antes do entrypoint atual.
if [ "$is_first_run" = "1" ] && [ -f /home/omni/.omni/data/postgres/PG_VERSION ]; then
  echo "Legacy volume detectado (pgdata existe sem backup) — limpando"
  su-exec omni rm -rf /home/omni/.omni/data/postgres
fi

if [ "$is_first_run" = "1" ]; then
  echo "Primeira execucao — rodando omni install"
  su-exec omni omni install \
    --port "$OMNI_PORT" \
    --api-key "$OMNI_API_KEY"
  # omni install inicia pgserve + omni server via PM2 daemon
else
  echo "Restart — restaurando state.tar.gz do backup"
  su-exec omni tar -xzf "$STATE_TAR" -C /home/omni
  echo "Restaurando processos PM2 via resurrect"
  su-exec omni pm2 resurrect || echo "WARN: pm2 resurrect falhou"
fi

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

if [ "$is_first_run" = "1" ]; then
  # Salvar dump pra restarts futuros poderem usar resurrect
  sleep 5
  su-exec omni pm2 save || echo "WARN: pm2 save falhou"

  # Tar tudo de .omni (sans /data/) e .pm2 pro volume persistente.
  # Pega config.json, nats-server binario, logs/, dump.pm2 — tudo que
  # o pm2 resurrect precisa pra subir omni-api + omni-nats no restart.
  echo "Salvando state.tar.gz com .omni (sans /data) + .pm2"
  su-exec omni tar -C /home/omni \
    --exclude='.omni/data' \
    -czf "$STATE_TAR" .omni .pm2
  echo "state.tar.gz OK ($(stat -c%s "$STATE_TAR") bytes)"
  su-exec omni touch "$INITIALIZED"
fi

# Mantem container vivo seguindo os logs PM2 em foreground.
# Saida do pm2 logs encerra o container; Docker reinicia
# (restart: unless-stopped) e o else branch acima ja extraiu o
# state.tar.gz do volume.
exec su-exec omni pm2 logs --raw --lines 0
