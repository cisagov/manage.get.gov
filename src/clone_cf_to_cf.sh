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

# Source (where to copy FROM)
SRC_SPACE_DEFAULT="staging"
SRC_SERVICE_DEFAULT=""   # derived from space if empty
SRC_APP_DEFAULT=""       # derived from space if empty

# Destination (where to copy TO)
DST_SPACE_DEFAULT=""
DST_SERVICE_DEFAULT=""   # derived from space if empty
DST_APP_DEFAULT=""       # derived from space if empty

# Local Docker Postgres target (compose service: db) - fallback if no --dst-space
LOCAL_DB_DEFAULT="app"
LOCAL_USER_DEFAULT="user"

TUNNEL_PORT_SRC_DEFAULT="65432"
TUNNEL_PORT_DST_DEFAULT="65433"

# -----------------------------
# Args
# -----------------------------
usage() {
  cat <<USAGE
Clone a Cloud.gov RDS Postgres to another Cloud.gov RDS or local Docker Postgres.

Usage:
  $(basename "$0") [options]

Source Options (copy FROM):
  --src-space SPACE         Source CF space (default: ${SRC_SPACE_DEFAULT})
  --src-service SERVICE     Source RDS service (default: derived: getgov-<space>-database)
  --src-app APP             Source app for SSH tunnel (default: derived: getgov-<space>)

Destination Options (copy TO):
  --dst-space SPACE         Destination CF space (if omitted, copies to local Docker)
  --dst-service SERVICE     Destination RDS service (default: derived: getgov-<space>-database)
  --dst-app APP             Destination app for SSH tunnel (default: derived: getgov-<space>)

Local Docker Options (used when --dst-space is not set):
  --local-db NAME           (default: ${LOCAL_DB_DEFAULT})
  --local-user USER         (default: ${LOCAL_USER_DEFAULT})

General Options:
  --org ORG                 CF org (default: ${ORG_DEFAULT})
  --schema-only             Dump/restore schema only (no data)
  --no-scrub                Skip PII scrub after restore
  -y                        Non-interactive cf actions where possible
  -h|--help

Examples:
  # Clone staging to local Docker (original behavior)
  $(basename "$0") --src-space staging

  # Clone staging to getgov-dg
  $(basename "$0") --src-space staging --dst-space dg

  # Clone production to staging
  $(basename "$0") --src-space production --dst-space staging
USAGE
}

ORG="${ORG_DEFAULT}"
SRC_SPACE="${SRC_SPACE_DEFAULT}"
SRC_SERVICE="${SRC_SERVICE_DEFAULT}"
SRC_APP="${SRC_APP_DEFAULT}"
DST_SPACE="${DST_SPACE_DEFAULT}"
DST_SERVICE="${DST_SERVICE_DEFAULT}"
DST_APP="${DST_APP_DEFAULT}"
LOCAL_DB="${LOCAL_DB_DEFAULT}"
LOCAL_USER="${LOCAL_USER_DEFAULT}"
TUNNEL_PORT_SRC="${TUNNEL_PORT_SRC_DEFAULT}"
TUNNEL_PORT_DST="${TUNNEL_PORT_DST_DEFAULT}"
SCHEMA_ONLY="no"
DO_SCRUB="yes"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --org) ORG="$2"; shift 2;;
    --src-space) SRC_SPACE="$2"; shift 2;;
    --src-service) SRC_SERVICE="$2"; shift 2;;
    --src-app) SRC_APP="$2"; shift 2;;
    --dst-space) DST_SPACE="$2"; shift 2;;
    --dst-service) DST_SERVICE="$2"; shift 2;;
    --dst-app) DST_APP="$2"; shift 2;;
    --local-db) LOCAL_DB="$2"; shift 2;;
    --local-user) LOCAL_USER="$2"; shift 2;;
    --schema-only) SCHEMA_ONLY="yes"; shift 1;;
    --no-scrub) DO_SCRUB="no"; shift 1;;
    -y) shift 1;;  # placeholder for future non-interactive support
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

# Source derivation
if [[ -z "${SRC_SERVICE:-}" || -z "${SRC_APP:-}" ]]; then
  IFS='|' read -r _svc _app < <(derive_from_space "${SRC_SPACE}")
  [[ -z "${SRC_SERVICE:-}" ]] && SRC_SERVICE="$_svc"
  [[ -z "${SRC_APP:-}" ]] && SRC_APP="$_app"
fi

# Destination derivation (only if dst-space is set)
COPY_TO_CF="no"
if [[ -n "${DST_SPACE}" ]]; then
  COPY_TO_CF="yes"
  if [[ -z "${DST_SERVICE:-}" || -z "${DST_APP:-}" ]]; then
    IFS='|' read -r _svc _app < <(derive_from_space "${DST_SPACE}")
    [[ -z "${DST_SERVICE:-}" ]] && DST_SERVICE="$_svc"
    [[ -z "${DST_APP:-}" ]] && DST_APP="$_app"
  fi
fi

echo ">> Source: org=${ORG} space=${SRC_SPACE} service=${SRC_SERVICE} app=${SRC_APP}"
if [[ "$COPY_TO_CF" == "yes" ]]; then
  echo ">> Destination: space=${DST_SPACE} service=${DST_SERVICE} app=${DST_APP}"
else
  echo ">> Destination: local Docker service=db user=${LOCAL_USER} db=${LOCAL_DB}"
fi

# Safety check: prevent copying to production
if [[ "$COPY_TO_CF" == "yes" && "${DST_SPACE}" == "production" ]]; then
  echo "!! SAFETY: Refusing to overwrite production database."
  echo "   If you really need to do this, manually edit the script."
  exit 1
fi

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

# Only check Docker db service if copying to local
if [[ "$COPY_TO_CF" == "no" ]]; then
  if ! $DC ps --format '{{.Service}} {{.Status}}' 2>/dev/null | awk '$1=="db"{print $2}' | grep -qi 'Up'; then
    echo "!! Docker service 'db' is not running. Start it:"
    echo "   $DC up -d db"
    exit 1
  fi
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
echo ">> Targeting org=${ORG} space=${SRC_SPACE}"
cf target -o "${ORG}" -s "${SRC_SPACE}" >/dev/null 2>&1 || true

CF_API="$(cf api | awk 'NR==1{print $3}')"
if [[ "$CF_API" != "api.fr.cloud.gov" ]]; then
  echo ">> Logging into Cloud.gov…"
  cf login -a api.fr.cloud.gov --sso
  cf target -o "${ORG}" -s "${SRC_SPACE}"
fi

# -----------------------------
# Fetch SOURCE service creds via service-key
# -----------------------------
SRC_KEY_NAME="clone-key-src-$(date +%s)"
echo ">> Creating source service key ${SRC_KEY_NAME} for ${SRC_SERVICE}…"
set +e; cf create-service-key "${SRC_SERVICE}" "${SRC_KEY_NAME}" >/dev/null 2>&1; set -e

echo ">> Retrieving source service key JSON…"
SRC_SERVICE_JSON="$(cf service-key "${SRC_SERVICE}" "${SRC_KEY_NAME}" | sed -n '/{/,$p')"
SRC_CREDS_JSON="$(echo "$SRC_SERVICE_JSON" | jq -c '.credentials // .')"

SRC_HOST="$(echo "$SRC_CREDS_JSON" | jq -r '.hostname // .host // empty')"
SRC_PORT="$(echo "$SRC_CREDS_JSON" | jq -r '.port // 5432 | tostring')"
SRC_DB_NAME="$(echo "$SRC_CREDS_JSON" | jq -r '.dbname // .db_name // .name // empty')"
SRC_USERNAME="$(echo "$SRC_CREDS_JSON" | jq -r '.username // .user // empty')"
SRC_PASSWORD="$(echo "$SRC_CREDS_JSON" | jq -r '.password // .pass // empty')"
SRC_URI="$(echo "$SRC_CREDS_JSON" | jq -r '.uri // empty')"

# Fallback parse from URI if needed
if [[ -z "$SRC_HOST" && -n "$SRC_URI" ]]; then SRC_HOST="$(echo "$SRC_URI" | sed -E 's#^postgres(ql)?://[^@]+@([^:/]+).*#\2#')"; fi
if [[ -z "$SRC_PORT" && -n "$SRC_URI" ]]; then SRC_PORT="$(echo "$SRC_URI" | sed -E 's#^.*:([0-9]+)/.*#\1#')"; fi
if [[ -z "$SRC_DB_NAME" && -n "$SRC_URI" ]]; then SRC_DB_NAME="$(echo "$SRC_URI" | sed -E 's#^.*/([^/?]+).*#\1#')"; fi
if [[ -z "$SRC_USERNAME" && -n "$SRC_URI" ]]; then SRC_USERNAME="$(echo "$SRC_URI" | sed -E 's#^postgres(ql)?://([^:]+):.*#\2#')"; fi
if [[ -z "$SRC_PASSWORD" && -n "$SRC_URI" ]]; then SRC_PASSWORD="$(echo "$SRC_URI" | sed -E 's#^postgres(ql)?://[^:]+:([^@]+)@.*#\2#')"; fi

if [[ -z "$SRC_HOST" || -z "$SRC_PORT" || -z "$SRC_DB_NAME" || -z "$SRC_USERNAME" || -z "$SRC_PASSWORD" ]]; then
  echo "!! Could not parse source DB credentials from service key. Raw:"; echo "$SRC_SERVICE_JSON"; exit 1
fi
echo ">> Source DB: host=${SRC_HOST} port=${SRC_PORT} db=${SRC_DB_NAME} user=${SRC_USERNAME}"

# -----------------------------
# Fetch DESTINATION service creds (if copying to CF)
# -----------------------------
DST_KEY_NAME=""
DST_HOST=""
DST_PORT=""
DST_DB_NAME=""
DST_USERNAME=""
DST_PASSWORD=""

if [[ "$COPY_TO_CF" == "yes" ]]; then
  echo ">> Targeting destination space=${DST_SPACE}"
  cf target -o "${ORG}" -s "${DST_SPACE}" >/dev/null

  DST_KEY_NAME="clone-key-dst-$(date +%s)"
  echo ">> Creating destination service key ${DST_KEY_NAME} for ${DST_SERVICE}…"
  set +e; cf create-service-key "${DST_SERVICE}" "${DST_KEY_NAME}" >/dev/null 2>&1; set -e

  echo ">> Retrieving destination service key JSON…"
  DST_SERVICE_JSON="$(cf service-key "${DST_SERVICE}" "${DST_KEY_NAME}" | sed -n '/{/,$p')"
  DST_CREDS_JSON="$(echo "$DST_SERVICE_JSON" | jq -c '.credentials // .')"

  DST_HOST="$(echo "$DST_CREDS_JSON" | jq -r '.hostname // .host // empty')"
  DST_PORT="$(echo "$DST_CREDS_JSON" | jq -r '.port // 5432 | tostring')"
  DST_DB_NAME="$(echo "$DST_CREDS_JSON" | jq -r '.dbname // .db_name // .name // empty')"
  DST_USERNAME="$(echo "$DST_CREDS_JSON" | jq -r '.username // .user // empty')"
  DST_PASSWORD="$(echo "$DST_CREDS_JSON" | jq -r '.password // .pass // empty')"
  DST_URI="$(echo "$DST_CREDS_JSON" | jq -r '.uri // empty')"

  # Fallback parse from URI
  if [[ -z "$DST_HOST" && -n "$DST_URI" ]]; then DST_HOST="$(echo "$DST_URI" | sed -E 's#^postgres(ql)?://[^@]+@([^:/]+).*#\2#')"; fi
  if [[ -z "$DST_PORT" && -n "$DST_URI" ]]; then DST_PORT="$(echo "$DST_URI" | sed -E 's#^.*:([0-9]+)/.*#\1#')"; fi
  if [[ -z "$DST_DB_NAME" && -n "$DST_URI" ]]; then DST_DB_NAME="$(echo "$DST_URI" | sed -E 's#^.*/([^/?]+).*#\1#')"; fi
  if [[ -z "$DST_USERNAME" && -n "$DST_URI" ]]; then DST_USERNAME="$(echo "$DST_URI" | sed -E 's#^postgres(ql)?://([^:]+):.*#\2#')"; fi
  if [[ -z "$DST_PASSWORD" && -n "$DST_URI" ]]; then DST_PASSWORD="$(echo "$DST_URI" | sed -E 's#^postgres(ql)?://[^:]+:([^@]+)@.*#\2#')"; fi

  if [[ -z "$DST_HOST" || -z "$DST_PORT" || -z "$DST_DB_NAME" || -z "$DST_USERNAME" || -z "$DST_PASSWORD" ]]; then
    echo "!! Could not parse destination DB credentials from service key. Raw:"; echo "$DST_SERVICE_JSON"; exit 1
  fi
  echo ">> Destination DB: host=${DST_HOST} port=${DST_PORT} db=${DST_DB_NAME} user=${DST_USERNAME}"
fi

# -----------------------------
# Check apps exist & SSH is enabled
# -----------------------------
check_app_ssh() {
  local space="$1"
  local app="$2"
  
  cf target -o "${ORG}" -s "${space}" >/dev/null
  
  if ! cf app "${app}" >/dev/null 2>&1; then
    echo "!! App '${app}' not found in ${ORG}/${space}."
    exit 1
  fi
  if ! cf apps | awk -v a="$app" 'NR>3 && $1==a {print $2}' | grep -qx "started"; then
    echo "!! App '${app}' is not 'started' in ${space}."; exit 1
  fi
  if ! cf ssh-enabled "${app}" 2>/dev/null | grep -qi 'enabled'; then
    echo "!! SSH is not enabled on '${app}'. Enable with:"; echo "   cf enable-ssh ${app} && cf restart ${app}"; exit 1
  fi
}

echo ">> Checking source app SSH…"
check_app_ssh "${SRC_SPACE}" "${SRC_APP}"

if [[ "$COPY_TO_CF" == "yes" ]]; then
  echo ">> Checking destination app SSH…"
  check_app_ssh "${DST_SPACE}" "${DST_APP}"
fi

# -----------------------------
# Cleanup handler
# -----------------------------
SSH_PID_SRC=""
SSH_PID_DST=""

cleanup() {
  echo ">> Cleaning up…"
  if [[ -n "${SSH_PID_SRC:-}" ]]; then
    echo "   Closing source SSH tunnel (pid=${SSH_PID_SRC})"
    kill "$SSH_PID_SRC" 2>/dev/null || true
  fi
  if [[ -n "${SSH_PID_DST:-}" ]]; then
    echo "   Closing destination SSH tunnel (pid=${SSH_PID_DST})"
    kill "$SSH_PID_DST" 2>/dev/null || true
  fi
  if [[ -n "${SRC_KEY_NAME:-}" ]]; then
    echo "   Deleting source service key ${SRC_KEY_NAME}"
    cf target -o "${ORG}" -s "${SRC_SPACE}" >/dev/null 2>&1 || true
    cf delete-service-key -f "${SRC_SERVICE}" "${SRC_KEY_NAME}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${DST_KEY_NAME:-}" ]]; then
    echo "   Deleting destination service key ${DST_KEY_NAME}"
    cf target -o "${ORG}" -s "${DST_SPACE}" >/dev/null 2>&1 || true
    cf delete-service-key -f "${DST_SERVICE}" "${DST_KEY_NAME}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# -----------------------------
# Open SSH tunnels
# -----------------------------
echo ">> Starting source SSH tunnel: localhost:${TUNNEL_PORT_SRC} -> ${SRC_HOST}:${SRC_PORT} via ${SRC_APP}"
cf target -o "${ORG}" -s "${SRC_SPACE}" >/dev/null
cf ssh "${SRC_APP}" -N -L "${TUNNEL_PORT_SRC}:${SRC_HOST}:${SRC_PORT}" -T &
SSH_PID_SRC=$!

if [[ "$COPY_TO_CF" == "yes" ]]; then
  echo ">> Starting destination SSH tunnel: localhost:${TUNNEL_PORT_DST} -> ${DST_HOST}:${DST_PORT} via ${DST_APP}"
  cf target -o "${ORG}" -s "${DST_SPACE}" >/dev/null
  cf ssh "${DST_APP}" -N -L "${TUNNEL_PORT_DST}:${DST_HOST}:${DST_PORT}" -T &
  SSH_PID_DST=$!
fi

# Wait for tunnels to be ready
for i in {1..30}; do nc -z 127.0.0.1 "${TUNNEL_PORT_SRC}" 2>/dev/null && break; sleep 1; done
nc -z 127.0.0.1 "${TUNNEL_PORT_SRC}" 2>/dev/null || { echo "!! Source tunnel did not open."; exit 1; }

if [[ "$COPY_TO_CF" == "yes" ]]; then
  for i in {1..30}; do nc -z 127.0.0.1 "${TUNNEL_PORT_DST}" 2>/dev/null && break; sleep 1; done
  nc -z 127.0.0.1 "${TUNNEL_PORT_DST}" 2>/dev/null || { echo "!! Destination tunnel did not open."; exit 1; }
fi

# -----------------------------
# Detect server major with dockerized psql
# -----------------------------
echo ">> Detecting source server version via Docker psql…"
SERVER_MAJOR="$(
  docker run --rm \
    -e PGPASSWORD="${SRC_PASSWORD}" \
    "postgres:15-alpine" \
    psql -h "${DOCKER_HOSTNAME}" -p "${TUNNEL_PORT_SRC}" -U "${SRC_USERNAME}" -d "${SRC_DB_NAME}" -At -c 'show server_version' 2>/dev/null \
  | awk -F. '{print $1}'
)"
[[ -z "$SERVER_MAJOR" ]] && SERVER_MAJOR="15"
IMAGE_TAG="${SERVER_MAJOR}-alpine"
echo ">> Using docker image postgres:${IMAGE_TAG} for pg_dump/psql"

# -----------------------------
# Reset destination schema
# -----------------------------
if [[ "$COPY_TO_CF" == "yes" ]]; then
  echo ">> Resetting schema in destination CF database (${DST_SPACE}/${DST_DB_NAME})…"
  docker run --rm \
    -e PGPASSWORD="${DST_PASSWORD}" \
    "postgres:${IMAGE_TAG}" \
    psql -h "${DOCKER_HOSTNAME}" -p "${TUNNEL_PORT_DST}" -U "${DST_USERNAME}" -d "${DST_DB_NAME}" -v ON_ERROR_STOP=1 <<'SQL'
DO $$BEGIN
  IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='public') THEN
    EXECUTE 'DROP SCHEMA public CASCADE';
  END IF;
END$$;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO PUBLIC;
SQL
else
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
fi

# -----------------------------
# Dump from source -> restore to destination
# -----------------------------
echo ">> Streaming pg_dump from source -> psql to destination…"
DUMP_FMT_ARGS="-Fp --no-owner --no-privileges"
[[ "$SCHEMA_ONLY" == "yes" ]] && DUMP_FMT_ARGS="-Fp --schema-only"

if [[ "$COPY_TO_CF" == "yes" ]]; then
  # CF to CF: pipe between two docker runs
  docker run --rm \
    -e PGPASSWORD="${SRC_PASSWORD}" \
    "postgres:${IMAGE_TAG}" \
    pg_dump -h "${DOCKER_HOSTNAME}" -p "${TUNNEL_PORT_SRC}" -U "${SRC_USERNAME}" -d "${SRC_DB_NAME}" ${DUMP_FMT_ARGS} -v \
  | docker run --rm -i \
    -e PGPASSWORD="${DST_PASSWORD}" \
    "postgres:${IMAGE_TAG}" \
    psql -h "${DOCKER_HOSTNAME}" -p "${TUNNEL_PORT_DST}" -U "${DST_USERNAME}" -d "${DST_DB_NAME}" -v ON_ERROR_STOP=1
else
  # CF to local Docker
  docker run --rm \
    -e PGPASSWORD="${SRC_PASSWORD}" \
    "postgres:${IMAGE_TAG}" \
    pg_dump -h "${DOCKER_HOSTNAME}" -p "${TUNNEL_PORT_SRC}" -U "${SRC_USERNAME}" -d "${SRC_DB_NAME}" ${DUMP_FMT_ARGS} -v \
  | $DC exec -T db psql -U "${LOCAL_USER}" -d "${LOCAL_DB}" -v ON_ERROR_STOP=1
fi

echo ">> Database copy complete."

# -----------------------------
# PII Scrub
# -----------------------------
if [[ "$DO_SCRUB" == "yes" ]]; then
  echo ">> Running PII scrub…"
  if [[ "$COPY_TO_CF" == "yes" ]]; then
    # Run scrub on the destination app
    cf target -o "${ORG}" -s "${DST_SPACE}" >/dev/null
    cf run-task "${DST_APP}" --command "./manage.py clean_up_pii" --name "pii-scrub-$(date +%s)"
    echo ">> PII scrub task submitted to ${DST_APP}. Check 'cf tasks ${DST_APP}' for status."
  else
    $DC exec -T app ./manage.py clean_up_pii
    echo ">> Scrub complete."
  fi
else
  echo ">> Skipping PII scrub (--no-scrub specified)"
fi

echo ""
echo "=== Done ==="
if [[ "$COPY_TO_CF" == "yes" ]]; then
  echo "Copied: ${SRC_SPACE}/${SRC_SERVICE} -> ${DST_SPACE}/${DST_SERVICE}"
else
  echo "Copied: ${SRC_SPACE}/${SRC_SERVICE} -> local Docker db"
fi