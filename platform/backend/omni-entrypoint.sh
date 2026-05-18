#!/bin/bash
set -e

# Garantir ownership do home do omni (volume pode vir com root)
chown -R omni:omni /home/omni

# Volume `flowertex_omnidata:/home/omni/.omni/data` so persiste o DB
# do postgres. `config.json` e o PM2 dump (.pm2/dump.pm2) ficam fora
# do volume e somem no restart. Sem eles, o pm2-runtime nao encontra
# os processos registrados e o container entra em crashloop com
# "process name not found".
#
# Estrategia: backup desses arquivos no proprio data volume (que
# persiste) e restore antes do pm2 resurrect no restart.
BACKUP_DIR=/home/omni/.omni/data/.entrypoint_backup
CONFIG_BAK="$BACKUP_DIR/config.json"
PM2_DUMP_BAK="$BACKUP_DIR/pm2.dump"
CONFIG_PATH=/home/omni/.omni/config.json
PM2_DUMP_PATH=/home/omni/.pm2/dump.pm2

su-exec omni mkdir -p "$BACKUP_DIR"

is_first_run=0
if [ ! -f "$BACKUP_DIR/.initialized" ]; then
  is_first_run=1
fi

# Legacy volume detection: postgres data existe (PG_VERSION) mas
# nao temos .initialized (volume foi criado antes desta entrypoint).
# Sem backup do config/pm2 dump, e impossivel resurrect — limpa o
# volume e reinstala fresh.
if [ "$is_first_run" = "1" ] && [ -f /home/omni/.omni/data/postgres/PG_VERSION ]; then
  echo "Legacy volume detectado (postgres existe mas sem backup) — limpando"
  su-exec omni rm -rf /home/omni/.omni/data/postgres /home/omni/.omni/data/.entrypoint_backup
  su-exec omni mkdir -p "$BACKUP_DIR"
fi

if [ "$is_first_run" = "1" ]; then
  echo "Primeira execucao — rodando omni install"
  su-exec omni omni install \
    --port "$OMNI_PORT" \
    --api-key "$OMNI_API_KEY"
  # omni install inicia pgserve + omni server via PM2 daemon
else
  echo "Restart — restaurando config + pm2 dump do backup"
  # pm2 dump tem paths absolutos pros log files (.omni/logs/*.log).
  # No recreate o container vem fresh: so o volume .omni/data/ persiste,
  # entao a pasta logs/ some e pm2 resurrect falha com ENOENT silencioso
  # (tabela de processos fica vazia, pgserve nunca sobe e healthcheck
  # do compose estoura em 5min). Pre-criar a pasta resolve.
  su-exec omni mkdir -p /home/omni/.omni /home/omni/.omni/logs /home/omni/.pm2
  if [ -f "$CONFIG_BAK" ]; then
    su-exec omni cp "$CONFIG_BAK" "$CONFIG_PATH"
  else
    echo "WARN: config.json backup ausente — pgserve pode falhar"
  fi
  if [ -f "$PM2_DUMP_BAK" ]; then
    su-exec omni cp "$PM2_DUMP_BAK" "$PM2_DUMP_PATH"
    echo "Restaurando processos PM2 via resurrect"
    su-exec omni pm2 resurrect || echo "WARN: pm2 resurrect falhou"
  else
    echo "ERRO: pm2 dump backup ausente — container nao tem como saber quais processos iniciar"
    exit 1
  fi
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

  # Backup config + dump pro volume persistente
  if [ -f "$CONFIG_PATH" ]; then
    su-exec omni cp "$CONFIG_PATH" "$CONFIG_BAK"
    echo "config.json backup OK"
  fi
  if [ -f "$PM2_DUMP_PATH" ]; then
    su-exec omni cp "$PM2_DUMP_PATH" "$PM2_DUMP_BAK"
    echo "pm2 dump backup OK"
  fi
  su-exec omni touch "$BACKUP_DIR/.initialized"
fi

# Mantem container vivo seguindo os logs PM2 em foreground.
# Saida do pm2 logs encerra o container; Docker reinicia
# (restart: unless-stopped) e o else branch acima ja carregou
# o dump salvo no volume.
exec su-exec omni pm2 logs --raw --lines 0
