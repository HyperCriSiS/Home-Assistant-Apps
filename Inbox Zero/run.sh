#!/usr/bin/env bash
set -Eeuo pipefail

readonly OPTIONS_FILE="/data/options.json"
readonly PGDATA="/data/postgres"
readonly SECRETS_FILE="/data/secrets.env"

pids=()
postgres_pid=""

log_info() {
    printf '[INFO] %s\n' "$*"
}

log_error() {
    printf '[ERROR] %s\n' "$*" >&2
}

option() {
    jq -r "$1 // empty" "${OPTIONS_FILE}"
}

# export_option NAME JQ_PATH [DEFAULT]: empty, null and false fall back to DEFAULT.
export_option() {
    local value
    value="$(option "$2")"
    export "$1=${value:-${3:-}}"
}

# Next.js inlines NEXT_PUBLIC_ values at build time, so the image is built with
# placeholders. The upstream start script scans the whole build once per
# placeholder, which takes minutes on every start. This replaces all of them
# after a single scan in the same way; the upstream script then finds nothing
# left and remains the fallback.
replace_placeholders() {
    local pattern='(http://)?NEXT_PUBLIC_[A-Z0-9_]+_PLACEHOLDER'
    local match file placeholder name value last_file=""
    local -a plain_files=() sed_args=()
    local -A seen=()

    while IFS= read -r match; do
        [[ "${match}" =~ ^(.*):(${pattern})$ ]] || continue
        file="${BASH_REMATCH[1]}"
        placeholder="${BASH_REMATCH[2]}"
        name="${placeholder#http://}"
        name="${name%_PLACEHOLDER}"
        value="${!name:-}"
        if [[ "${file}" == *.rsc || "${file}" == *.html ]]; then
            # Prerendered pages carry length-prefixed payloads; upstream's
            # rewriter keeps those lengths correct.
            node docker/scripts/replace-in-prerender.mjs "${file}" "${placeholder}" "${value}" || true
            continue
        fi
        [[ "${file}" == "${last_file}" ]] || plain_files+=("${file}")
        last_file="${file}"
        [[ -z "${seen[${placeholder}]:-}" ]] || continue
        seen[${placeholder}]=1
        value="$(printf '%s' "${value}" | sed -e 's/[\\&|]/\\&/g')"
        # "http://NAME" has to be replaced before the bare "NAME" it contains.
        if [[ "${placeholder}" == http://* ]]; then
            sed_args=(-e "s|${placeholder}|${value}|g" "${sed_args[@]}")
        else
            sed_args+=(-e "s|${placeholder}|${value}|g")
        fi
    # Reverse order lists "http://NAME" before "NAME" within each file.
    done < <(grep -rHoE "${pattern}" apps/web/.next apps/web/public | sort -ur)

    if [[ ${#plain_files[@]} -gt 0 ]]; then
        sed -i "${sed_args[@]}" "${plain_files[@]}"
    fi
}

shutdown_processes() {
    local status="${1:-0}"

    trap - TERM INT EXIT
    for pid in "${pids[@]}"; do
        kill -TERM "${pid}" 2>/dev/null || true
    done
    if [[ -n "${postgres_pid}" ]]; then
        # SIGINT is PostgreSQL's fast shutdown: disconnects clients, then
        # writes a clean checkpoint.
        kill -INT "${postgres_pid}" 2>/dev/null || true
        wait "${postgres_pid}" 2>/dev/null || true
    fi
    exit "${status}"
}

trap 'shutdown_processes 0' TERM INT
trap 'shutdown_processes 1' EXIT

# --- Options -----------------------------------------------------------------

base_url="$(option '.base_url')"
base_url="${base_url%/}"
default_llms="$(option '.llm.default_models')"
allowed_emails="$(option '.auth.allowed_emails')"
google_client_id="$(option '.google.client_id')"
microsoft_client_id="$(option '.microsoft.client_id')"

if [[ -z "${default_llms}" ]]; then
    log_error "Set llm.default_models, for example openai:gpt-6-luna or ollama:qwen3.5:4b."
    exit 1
fi
if [[ -z "${google_client_id}" && -z "${microsoft_client_id}" && -z "${allowed_emails}" ]]; then
    log_error "Nobody could sign in: set auth.allowed_emails for password sign-in, or configure Google or Microsoft."
    exit 1
fi

# --- Secrets, generated once and kept in the App backup ----------------------

umask 077
touch "${SECRETS_FILE}"
for name in AUTH_SECRET EMAIL_ENCRYPT_SECRET EMAIL_ENCRYPT_SALT INTERNAL_API_KEY \
    API_KEY_SALT CRON_SECRET REDIS_HTTP_TOKEN; do
    if ! grep -q "^${name}=" "${SECRETS_FILE}"; then
        printf '%s=%s\n' "${name}" "$(openssl rand -hex 32)" >>"${SECRETS_FILE}"
    fi
done
umask 022
set -a
# shellcheck disable=SC1090
. "${SECRETS_FILE}"
set +a

# --- Environment of the Inbox Zero server ------------------------------------

export NODE_ENV="production"
# Docker sets HOSTNAME to the container ID; Next.js would bind to that only.
export HOSTNAME="0.0.0.0"
export PORT="3000"
export DATABASE_URL="postgresql://postgres@127.0.0.1:5432/inboxzero?schema=public"
export DIRECT_URL="${DATABASE_URL}"
export REDIS_URL="redis://127.0.0.1:6379"
export REDIS_HTTP_URL="http://127.0.0.1:8079"
export INTERNAL_API_URL="http://127.0.0.1:3000"
export NEXT_PUBLIC_BASE_URL="${base_url}"
export NEXT_PUBLIC_BYPASS_PREMIUM_CHECKS="true"
export NEXT_PUBLIC_EMAIL_SEND_ENABLED="true"
export DEFAULT_LLMS="${default_llms}"
export_option LLM_API_KEY '.llm.api_key'
export AUTH_ALLOWED_EMAILS="${allowed_emails}"
if [[ -n "${allowed_emails}" ]]; then
    export NEXT_PUBLIC_AUTH_PASSWORD_ENABLED="true"
fi

# Upstream expects the literal "skipped" when Google is not used.
export GOOGLE_CLIENT_ID="${google_client_id:-skipped}"
export_option GOOGLE_CLIENT_SECRET '.google.client_secret' skipped
export_option GOOGLE_PUBSUB_TOPIC_NAME '.google.pubsub_topic_name' skipped
export_option GOOGLE_PUBSUB_VERIFICATION_TOKEN '.google.pubsub_verification_token'
if [[ -n "${microsoft_client_id}" ]]; then
    export MICROSOFT_CLIENT_ID="${microsoft_client_id}"
    export_option MICROSOFT_CLIENT_SECRET '.microsoft.client_secret'
    export_option MICROSOFT_TENANT_ID '.microsoft.tenant_id' common
fi
if [[ -z "${google_client_id}" && -z "${microsoft_client_id}" ]]; then
    export NEXT_PUBLIC_IMAP_ONLY="true"
fi

export_option IMAP_ALLOW_PRIVATE_HOSTS '.imap.allow_private_hosts' false
export_option IMAP_ALLOW_PLAINTEXT '.imap.allow_plaintext' false
export_option IMAP_IDLE_ENABLED '.imap.idle_enabled' false

# Additional variables come last so they can override everything above.
while IFS= read -r assignment; do
    export "${assignment?}"
done < <(jq -r '.env_vars[]? | "\(.name)=\(.value)"' "${OPTIONS_FILE}")

# --- PostgreSQL ----------------------------------------------------------------

mkdir -p "${PGDATA}" /run/postgresql
chown -R postgres:postgres "${PGDATA}" /run/postgresql
chmod 0700 "${PGDATA}"
if [[ ! -s "${PGDATA}/PG_VERSION" ]]; then
    log_info "Creating the PostgreSQL database."
    # The server listens on the container's loopback interface only.
    su-exec postgres initdb --pgdata="${PGDATA}" --auth=trust --encoding=UTF8 --no-locale >/dev/null
fi
su-exec postgres postgres -D "${PGDATA}" -c listen_addresses=127.0.0.1 &
postgres_pid="$!"
for _ in $(seq 1 60); do
    pg_isready --quiet --host=127.0.0.1 --username=postgres && break
    sleep 1
done
if [[ -z "$(psql --host=127.0.0.1 --username=postgres --tuples-only --no-align \
    --command="SELECT 1 FROM pg_database WHERE datname = 'inboxzero'")" ]]; then
    createdb --host=127.0.0.1 --username=postgres inboxzero
fi

# --- Redis and its HTTP adapter (Inbox Zero uses the Upstash REST protocol) ---

su-exec redis redis-server --bind 127.0.0.1 --save "" --appendonly no --dir /tmp >/dev/null &
pids+=("$!")
# No Erlang distribution: the adapter then opens its HTTP port only, and every
# request needs the generated token.
RELEASE_DISTRIBUTION="none" SRH_MODE="env" SRH_TOKEN="${REDIS_HTTP_TOKEN}" SRH_PORT="8079" \
    SRH_CONNECTION_STRING="${REDIS_URL}" \
    su-exec nobody /opt/redis-http/bin/prod start &
pids+=("$!")

# --- Inbox Zero ----------------------------------------------------------------

log_info "Starting Inbox Zero for ${NEXT_PUBLIC_BASE_URL}."
cd /app
replace_placeholders
/app/docker/scripts/start.sh &
pids+=("$!")
/usr/local/bin/cron.sh &
pids+=("$!")

# Every process is required; if one exits, stop so the Supervisor restarts the App.
wait -n "${postgres_pid}" "${pids[@]}" || true
log_error "A required process exited."
shutdown_processes 1
