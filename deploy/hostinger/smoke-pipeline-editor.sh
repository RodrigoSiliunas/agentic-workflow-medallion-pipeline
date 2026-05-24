#!/usr/bin/env bash
# Smoke check — Pipeline Editor no VPS Flowertex.
#
# Linux/macOS:
#   ssh hostinger-vps 'bash -s' < deploy/hostinger/smoke-pipeline-editor.sh
#
# PowerShell (stdin redirect nao funciona):
#   scp deploy/hostinger/smoke-pipeline-editor.sh hostinger-vps:/tmp/smoke-pipeline-editor.sh
#   ssh hostinger-vps "sed -i 's/\r$//' /tmp/smoke-pipeline-editor.sh && bash /tmp/smoke-pipeline-editor.sh
#
# Opcional (checks autenticados):
#   export SMOKE_API_TOKEN="eyJ..."
#   export SMOKE_PIPELINE_ID="uuid-do-pipeline"

set -uo pipefail

BASE_URL="${SMOKE_BASE_URL:-https://flowertex.idlehub.com.br}"
API="${BASE_URL}/api/v1"
PASS=0
FAIL=0
WARN=0

ok()   { echo "  [OK]   $*"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $*"; FAIL=$((FAIL + 1)); }
warn() { echo "  [WARN] $*"; WARN=$((WARN + 1)); }

section() { echo; echo "== $* =="; }

section "1. Infra (docker)"
if docker compose -f /opt/flowertex/docker-compose.yml ps 2>/dev/null | grep -q "flowertex-backend.*healthy"; then
  ok "backend healthy"
else
  fail "backend nao healthy — rode: cd /opt/flowertex && docker compose ps"
fi

if docker compose -f /opt/flowertex/docker-compose.yml ps 2>/dev/null | grep -q "flowertex-frontend.*healthy"; then
  ok "frontend healthy"
else
  fail "frontend nao healthy"
fi

IMAGE_TAG="$(grep -E '^IMAGE_TAG=' /opt/flowertex/.env 2>/dev/null | cut -d= -f2- || true)"
if [ -n "$IMAGE_TAG" ]; then
  ok "IMAGE_TAG=${IMAGE_TAG}"
else
  warn "IMAGE_TAG nao encontrado em /opt/flowertex/.env"
fi

section "2. Health publico"
HTTP="$(curl -sf -o /dev/null -w '%{http_code}' "${BASE_URL}/health" 2>/dev/null || echo 000)"
if [ "$HTTP" = "200" ]; then
  ok "${BASE_URL}/health -> 200"
else
  fail "${BASE_URL}/health -> ${HTTP}"
fi

section "3. Codigo Pipeline Editor no container"
if docker exec flowertex-backend test -f /app/platform/backend/app/api/routes/pipeline_editor.py 2>/dev/null; then
  ok "pipeline_editor.py presente"
else
  fail "pipeline_editor.py ausente — merge + deploy necessarios (imagem antiga)"
fi

if docker exec flowertex-backend test -d /app/platform/backend/app/services/pipeline_editor 2>/dev/null; then
  ok "services/pipeline_editor/ presente"
else
  fail "services/pipeline_editor/ ausente"
fi

section "4. Migration Alembic"
CURRENT="$(docker exec -w /app/platform/backend flowertex-backend uv run alembic current 2>/dev/null | tail -1 || true)"
echo "  current: ${CURRENT:-desconhecido}"

if echo "$CURRENT" | grep -q "d4e5f6a7b8c9"; then
  ok "migration d4e5f6a7b8c9 (pipeline editor) aplicada"
elif echo "$CURRENT" | grep -q "c0b1d2e3f4a5"; then
  fail "head c0b1 apenas — falta d4e5f6a7b8c9 (redeploy backend apos merge)"
else
  warn "revision inesperada: $CURRENT"
fi

TABLES="$(docker exec flowertex-postgres psql -U flowertex -d flowertex -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_name LIKE 'pipeline_edit%' OR table_name = 'pipeline_shares'" 2>/dev/null | tr -d ' ' || true)"
if [ "${TABLES:-0}" -ge 5 ]; then
  ok "tabelas pipeline editor no Postgres (${TABLES})"
elif [ "${TABLES:-0}" -gt 0 ]; then
  warn "apenas ${TABLES} tabela(s) pipeline editor"
else
  fail "nenhuma tabela pipeline editor — migration nao rodou"
fi

section "5. Rotas API"
# -s (sem -f) garante que curl nao exite com erro em 4xx — assim -w escreve
# o code limpo e o `|| echo 000` so dispara em erro real (timeout/DNS).
OPENAPI_CODE="$(curl -s -o /dev/null -w '%{http_code}' "${API}/openapi.json" 2>/dev/null || echo 000)"
if [ "$OPENAPI_CODE" = "404" ] || [ "$OPENAPI_CODE" = "000" ]; then
  warn "OpenAPI desabilitado em prod (DEBUG=false) — probe rotas protegidas"
  # 401/403/404 autenticado = rota existe; 405 = metodo errado mas rota existe
  EDIT_CODE="$(curl -sf -o /dev/null -w '%{http_code}' "${API}/pipelines/00000000-0000-0000-0000-000000000001/edit-sessions" 2>/dev/null || echo 000)"
  SHARE_CODE="$(curl -sf -o /dev/null -w '%{http_code}' "${API}/shared/pipeline-edit/smoke-token" 2>/dev/null || echo 000)"
  if [ "$EDIT_CODE" = "401" ] || [ "$EDIT_CODE" = "403" ]; then
    ok "edit-sessions responde ${EDIT_CODE} (rota registrada)"
  else
    fail "edit-sessions -> ${EDIT_CODE} (esperado 401/403 sem token)"
  fi
  if [ "$SHARE_CODE" = "404" ] || [ "$SHARE_CODE" = "200" ]; then
    ok "shared/pipeline-edit responde ${SHARE_CODE}"
  else
    fail "shared/pipeline-edit -> ${SHARE_CODE}"
  fi
else
  OPENAPI="$(curl -sf "${API}/openapi.json" 2>/dev/null || true)"
  if echo "$OPENAPI" | grep -q "edit-sessions"; then
    ok "rotas edit-sessions no OpenAPI"
  else
    fail "rotas edit-sessions ausentes no OpenAPI"
  fi
  if echo "$OPENAPI" | grep -q "shared/pipeline-edit"; then
    ok "rota share publica no OpenAPI"
  else
    fail "rota share ausente"
  fi
fi

section "6. Frontend (rotas Nuxt)"
for path in "/pipelines/smoke-test-id" "/shared/pipeline-edit/smoke-token"; do
  CODE="$(curl -sf -o /dev/null -w '%{http_code}' "${BASE_URL}${path}" 2>/dev/null || echo 000)"
  # 200 ou 302 (redirect login) indicam rota existente no Nuxt
  if [ "$CODE" = "200" ] || [ "$CODE" = "302" ]; then
    ok "${path} -> ${CODE}"
  else
    fail "${path} -> ${CODE}"
  fi
done

section "7. API autenticada (opcional)"
if [ -z "${SMOKE_API_TOKEN:-}" ] || [ -z "${SMOKE_PIPELINE_ID:-}" ]; then
  warn "SMOKE_API_TOKEN / SMOKE_PIPELINE_ID nao definidos — pulando checks autenticados"
  warn "Token NAO fica em localStorage (seguranca). Opcoes:"
  warn "  1) F12 -> Network -> request /api/v1/... -> Header Authorization: Bearer ..."
  warn "  2) curl -X POST ${API}/auth/login -H 'Content-Type: application/json' -d '{\"email\":\"...\",\"password\":\"...\"}'"
else
  AUTH="Authorization: Bearer ${SMOKE_API_TOKEN}"

  WS_CODE="$(curl -sf -o /tmp/smoke-ws.json -w '%{http_code}' \
    -H "$AUTH" "${API}/pipelines/${SMOKE_PIPELINE_ID}" 2>/dev/null || echo 000)"
  if [ "$WS_CODE" = "200" ]; then
    ok "GET workspace -> 200"
    if grep -q '"editor_scope"' /tmp/smoke-ws.json 2>/dev/null; then
      ok "editor_scope Silver presente"
    else
      fail "editor_scope ausente no workspace"
    fi
    NODES="$(python3 -c "import json; d=json.load(open('/tmp/smoke-ws.json')); print(len(d.get('manifest',{}).get('nodes',[])))" 2>/dev/null || echo 0)"
    if [ "${NODES:-0}" -gt 0 ]; then
      ok "manifest com ${NODES} no(s) Silver"
    else
      warn "manifest sem nos Silver (template nao WhatsApp?)"
    fi
  else
    fail "GET workspace -> ${WS_CODE}"
  fi

  SESS_CODE="$(curl -sf -o /tmp/smoke-sess.json -w '%{http_code}' \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"title":"Smoke test"}' \
    "${API}/pipelines/${SMOKE_PIPELINE_ID}/edit-sessions" 2>/dev/null || echo 000)"
  if [ "$SESS_CODE" = "201" ]; then
    ok "POST edit-session -> 201"
    SESSION_ID="$(python3 -c "import json; print(json.load(open('/tmp/smoke-sess.json'))['id'])" 2>/dev/null || true)"
    if [ -n "$SESSION_ID" ]; then
      ok "session_id=${SESSION_ID}"
    fi
  else
    fail "POST edit-session -> ${SESS_CODE}"
  fi
fi

section "Resumo"
echo "  PASS=${PASS}  FAIL=${FAIL}  WARN=${WARN}"
if [ "$FAIL" -gt 0 ]; then
  echo
  echo "Falhas detectadas. Se pipeline_editor ausente: merge main -> release-flowertex -> deploy-flowertex."
  echo "Apos deploy, migration d4e5f6a7b8c9 deve aplicar no restart do backend (entrypoint.sh)."
  exit 1
fi
exit 0
