#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# Load .env (for DATABASE_URL and other vars)
# -----------------------------
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# -----------------------------
# Defaults
# -----------------------------
ORG_DEFAULT="cisa-dotgov"
SPACE_DEFAULT="staging"   # source CF space with the RDS
TUNNEL_PORT_DEFAULT="65432"
SERVICE_DEFAULT=""   # derived from space if empty
APP_DEFAULT=""  # derived from space if empty

# Local Docker Postgres target (compose service: db)
LOCAL_DB_DEFAULT="app"
LOCAL_USER_DEFAULT="user"

# -----------------------------
# Args
# -----------------------------
usage() {
  cat <<USAGE
Clone a Cloud.gov RDS Postgres into your local Docker Postgres (compose service: db)
using a CF SSH tunnel + dockerized pg_dump (no local pg tools required).

Usage:
  $(basename "$0") [options]

Options:
  --space SPACE             (default: ${SPACE_DEFAULT})
  --service SERVICE         (default: derived: getgov-<space>-database)
  --app APP                 (default: derived: getgov-<space>)
  --tunnel-port PORT        (default: ${TUNNEL_PORT_DEFAULT})
  --local-db NAME           (default: ${LOCAL_DB_DEFAULT})
  --local-user USER         (default: ${LOCAL_USER_DEFAULT})
  --dump-file PATH          (optional: save a copy of SQL dump)
  --keep-dump               (keep dump file if --dump-file set)
  --schema-only             (dump/restore schema only)
  -y                        (non-interactive cf actions where possible)
  -h|--help
USAGE
}

ORG="${ORG_DEFAULT}"
SPACE="${SPACE_DEFAULT}"
SERVICE="${SERVICE_DEFAULT}"
APP="${APP_DEFAULT}"
TUNNEL_PORT="${TUNNEL_PORT_DEFAULT}"
LOCAL_DB="${LOCAL_DB_DEFAULT}"
LOCAL_USER="${LOCAL_USER_DEFAULT}"
SCHEMA_ONLY="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --org) ORG="$2"; shift 2;;
    --space) SPACE="$2"; shift 2;;
    --service) SERVICE="$2"; shift 2;;
    --app) APP="$2"; shift 2;;
    --tunnel-port) TUNNEL_PORT="$2"; shift 2;;
    --local-db) LOCAL_DB="$2"; shift 2;;
    --local-user) LOCAL_USER="$2"; shift 2;;
    --schema-only) SCHEMA_ONLY="yes"; shift 1;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

# Derive SERVICE / APP from SPACE if not provided
derive_from_space() {
  local sp="$1"
  local svc="getgov-${sp}-database"
  local app="getgov-${sp}"
  echo "$svc|$app"
}
if [[ -z "${SERVICE:-}" || -z "${APP:-}" ]]; then
  IFS='|' read -r _svc _app < <(derive_from_space "${SPACE}")
  [[ -z "${SERVICE:-}" ]] && SERVICE="$_svc"
  [[ -z "${APP:-}" ]] && APP="$_app"
fi

echo ">> Using org=${ORG} space=${SPACE} service=${SERVICE} app=${APP} tunnel_port=${TUNNEL_PORT}"
echo ">> Docker restore target: service=db user=${LOCAL_USER} db=${LOCAL_DB}"

# -----------------------------
# Host prerequisites
# -----------------------------
require_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1"; exit 1; }; }
for c in cf jq docker; do require_cmd "$c"; done

# Pick docker compose flavor
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "!! Neither 'docker compose' nor 'docker-compose' found."; exit 1
fi

# Ensure Docker "db" service is running
if ! $DC ps --format '{{.Service}} {{.Status}}' 2>/dev/null | awk '$1=="db"{print $2}' | grep -qi 'Up'; then
  echo "!! Docker service 'db' is not running. Start it:"
  echo "   $DC up -d db"
  exit 1
fi

# Docker connectivity to host (macOS needs host.docker.internal)
OS="$(uname -s)"
if [[ "$OS" == "Darwin" ]]; then
  DOCKER_HOSTNAME="host.docker.internal"
else
  DOCKER_HOSTNAME="127.0.0.1"
fi

# -----------------------------
# CF login / target
# -----------------------------
echo ">> Targeting org=${ORG} space=${SPACE}"
cf target -o "${ORG}" -s "${SPACE}" >/dev/null 2>&1 || true

CF_API="$(cf api | awk 'NR==1{print $3}')"
if [[ "$CF_API" != "api.fr.cloud.gov" ]]; then
  echo ">> Logging into Cloud.gov…"
  cf login -a api.fr.cloud.gov --sso
  cf target -o "${ORG}" -s "${SPACE}"
fi

# -----------------------------
# Fetch service creds via service-key
# -----------------------------
KEY_NAME="clone-key-$(date +%s)"
echo ">> Creating service key ${KEY_NAME} for ${SERVICE}…"
set +e; cf create-service-key "${SERVICE}" "${KEY_NAME}" >/dev/null 2>&1; set -e

echo ">> Retrieving service key JSON…"
SERVICE_JSON="$(cf service-key "${SERVICE}" "${KEY_NAME}" | sed -n '/{/,$p')"
CREDS_JSON="$(echo "$SERVICE_JSON" | jq -c '.credentials // .')"

HOST="$(echo "$CREDS_JSON" | jq -r '.hostname // .host // empty')"
PORT="$(echo "$CREDS_JSON" | jq -r '.port // 5432 | tostring')"
DB_NAME="$(echo "$CREDS_JSON" | jq -r '.dbname // .db_name // .name // empty')"
USERNAME="$(echo "$CREDS_JSON" | jq -r '.username // .user // empty')"
PASSWORD="$(echo "$CREDS_JSON" | jq -r '.password // .pass // empty')"
URI="$(echo   "$CREDS_JSON" | jq -r '.uri // empty')"

# Fallback parse from URI if needed
if [[ -z "$HOST" && -n "$URI" ]]; then HOST="$(echo "$URI" | sed -E 's#^postgres(ql)?://[^@]+@([^:/]+).*#\2#')"; fi
if [[ -z "$PORT" && -n "$URI" ]]; then PORT="$(echo "$URI" | sed -E 's#^.*:([0-9]+)/.*#\1#')"; fi
if [[ -z "$DB_NAME" && -n "$URI" ]]; then DB_NAME="$(echo "$URI" | sed -E 's#^.*/([^/?]+).*#\1#')"; fi
if [[ -z "$USERNAME" && -n "$URI" ]]; then USERNAME="$(echo "$URI" | sed -E 's#^postgres(ql)?://([^:]+):.*#\2#')"; fi
if [[ -z "$PASSWORD" && -n "$URI" ]]; then PASSWORD="$(echo "$URI" | sed -E 's#^postgres(ql)?://[^:]+:([^@]+)@.*#\2#')"; fi

if [[ -z "$HOST" || -z "$PORT" || -z "$DB_NAME" || -z "$USERNAME" || -z "$PASSWORD" ]]; then
  echo "!! Could not parse DB credentials from service key. Raw:"; echo "$SERVICE_JSON"; exit 1
fi
echo ">> Remote: host=${HOST} port=${PORT} db=${DB_NAME} user=${USERNAME}"

# -----------------------------
# Check app exists & SSH is enabled
# -----------------------------
if ! cf app "${APP}" >/dev/null 2>&1; then
  echo "!! App '${APP}' not found in ${ORG}/${SPACE}."
  echo "   Pass --app or create a small app in the space."; exit 1
fi
if ! cf apps | awk -v a="$APP" 'NR>3 && $1==a {print $2}' | grep -qx "started"; then
  echo "!! App '${APP}' is not 'started'."; exit 1
fi
if ! cf ssh-enabled "${APP}" 2>/dev/null | grep -qi 'enabled'; then
  echo "!! SSH is not enabled on '${APP}'. Enable once out-of-band:"; echo "   cf enable-ssh ${APP} && cf restart ${APP}"; exit 1
fi

# -----------------------------
# Open SSH tunnel
# -----------------------------
echo ">> Starting SSH tunnel: localhost:${TUNNEL_PORT} -> ${HOST}:${PORT} via app ${APP}"
cf ssh "${APP}" -N -L "${TUNNEL_PORT}:${HOST}:${PORT}" -T &
SSH_PID=$!

cleanup() {
  if [[ -n "${SSH_PID:-}" ]]; then
    echo ">> Closing SSH tunnel (pid=${SSH_PID})"
    kill "$SSH_PID" 2>/dev/null || true
  fi
  if [[ -n "${KEY_NAME:-}" ]]; then
    echo ">> Deleting temporary service key ${KEY_NAME}"
    cf delete-service-key -f "${SERVICE}" "${KEY_NAME}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

for i in {1..30}; do nc -z 127.0.0.1 "${TUNNEL_PORT}" 2>/dev/null && break; sleep 1; done
nc -z 127.0.0.1 "${TUNNEL_PORT}" 2>/dev/null || { echo "!! Tunnel did not open."; exit 1; }

# -----------------------------
# Detect server major with dockerized psql
# -----------------------------
echo ">> Detecting server version via Docker psql…"
SERVER_MAJOR="$(
  docker run --rm \
    -e PGPASSWORD="${PASSWORD}" \
    "postgres:15-alpine" \
    psql -h "${DOCKER_HOSTNAME}" -p "${TUNNEL_PORT}" -U "${USERNAME}" -d "${DB_NAME}" -At -c 'show server_version' 2>/dev/null \
  | awk -F. '{print $1}'
)"
[[ -z "$SERVER_MAJOR" ]] && SERVER_MAJOR="15"
IMAGE_TAG="${SERVER_MAJOR}-alpine"
echo ">> Using docker image postgres:${IMAGE_TAG} for pg_dump"

# -----------------------------
# Reset local schema inside Docker Postgres
# -----------------------------
echo ">> Resetting schema in Docker Postgres (service: db, db=${LOCAL_DB}, user=${LOCAL_USER})…"
$DC exec -T db psql -U "${LOCAL_USER}" -d "${LOCAL_DB}" -v ON_ERROR_STOP=1 <<'SQL'
DO $$BEGIN
  IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='public') THEN
    EXECUTE 'DROP SCHEMA public CASCADE';
  END IF;
END$$;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO PUBLIC;
SQL

# -----------------------------
# Dump remotely via dockerized pg_dump over the tunnel -> restore into Docker db
# -----------------------------
echo ">> Streaming dockerized pg_dump -> docker psql…"
DUMP_FMT_ARGS="-Fp --no-owner --no-privileges"
[[ "$SCHEMA_ONLY" == "yes" ]] && DUMP_FMT_ARGS="-Fp --schema-only"

docker run --rm \
  -e PGPASSWORD="${PASSWORD}" \
  "postgres:${IMAGE_TAG}" \
  pg_dump -h "${DOCKER_HOSTNAME}" -p "${TUNNEL_PORT}" -U "${USERNAME}" -d "${DB_NAME}" ${DUMP_FMT_ARGS} -v \
| $DC exec -T db psql -U "${LOCAL_USER}" -d "${LOCAL_DB}" -v ON_ERROR_STOP=1

echo "Local Docker database is populated."

# Scrub
echo ">> Running PII scrub …"
$DC exec -T app ./manage.py clean_up_pii
echo "Scrub complete."