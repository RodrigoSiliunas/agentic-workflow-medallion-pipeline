#!/usr/bin/env bash
# Bootstrap one-shot do flowertex.idlehub.com.br no VPS Hostinger.
# Idempotente: pode rodar multiplas vezes sem quebrar (vhost re-escrito,
# certbot pula se cert ja existe).
#
# Pre-requisitos (validar antes):
#   - dig +short flowertex.idlehub.com.br retorna 72.60.142.196 (A record propagado)
#   - /opt/flowertex/docker-compose.yml ja foi scp-ado
#   - /opt/flowertex/.env ja foi preenchido (POSTGRES_PASSWORD/SECRET_KEY/ENCRYPTION_KEY)
#   - /opt/flowertex/nginx-flowertex.conf ja foi scp-ado
#   - Login ghcr.io ja configurado em /root/.docker/config.json
#
# Uso: ssh root@soulfocus.io 'cd /opt/flowertex && bash bootstrap.sh'

set -euo pipefail

DOMAIN="flowertex.idlehub.com.br"
EMAIL="${ACME_EMAIL:-admin@idlehub.com.br}"
PROJECT_DIR="/opt/flowertex"
VHOST_DIR="/opt/nginx-proxy/conf.d"

cd "$PROJECT_DIR"

echo "== [1/6] Garante network externa proxy-network =="
docker network inspect proxy-network >/dev/null 2>&1 || \
    docker network create proxy-network

echo ""
echo "== [2/6] Vhost HTTP-only pra validacao ACME =="
cat > "$VHOST_DIR/flowertex.conf" <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 200 "bootstrap pending\n";
        add_header Content-Type text/plain;
    }
}
EOF
docker exec nginx-proxy nginx -t
docker exec nginx-proxy nginx -s reload

echo ""
echo "== [3/6] Emite cert via certbot --webroot =="
docker exec certbot-global certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive \
    --no-eff-email \
    --keep-until-expiring

echo ""
echo "== [4/6] Swap vhost pra HTTPS =="
cp "$PROJECT_DIR/nginx-flowertex.conf" "$VHOST_DIR/flowertex.conf"
docker exec nginx-proxy nginx -t
docker exec nginx-proxy nginx -s reload

echo ""
echo "== [5/6] Pull + up do stack =="
docker compose pull
docker compose up -d --remove-orphans

echo ""
echo "== [6/6] Smoke check =="
sleep 15
docker compose ps
echo ""
for i in $(seq 1 6); do
    code=$(curl -fsS -o /dev/null -w "%{http_code}" "https://$DOMAIN/health" 2>/dev/null || echo "000")
    echo "  attempt $i: health=$code"
    [ "$code" = "200" ] && { echo "OK"; exit 0; }
    sleep 10
done
echo "WARN: health endpoint nao respondeu 200 — checar 'docker compose logs backend'"
exit 1
