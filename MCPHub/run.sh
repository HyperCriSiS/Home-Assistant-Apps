#!/usr/bin/env bash
set -Eeuo pipefail

readonly OPTIONS_FILE="/data/options.json"
readonly MCPHUB_DATA_DIR="/data/mcphub"
readonly SECRET_DIR="/data/secrets"
readonly JWT_SECRET_FILE="${SECRET_DIR}/mcphub_jwt_secret"
readonly HA_INGRESS_PROXY_SECRET_FILE="${SECRET_DIR}/mcphub_ha_ingress_proxy_secret"

mcphub_pid=""
nginx_pid=""
tunnel_control_pid=""
ha_mcp_pid=""
ha_mcp_restart_at=0

log_info() {
    printf '[INFO] %s\n' "$*"
}

log_warn() {
    printf '[WARN] %s\n' "$*" >&2
}

log_error() {
    printf '[ERROR] %s\n' "$*" >&2
}

option() {
    local key="$1"
    python3 - "${OPTIONS_FILE}" "${key}" <<'PY'
import json
import sys

path, key = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

for group in ("openai", "remote_access", "home_assistant", "ha_mcp", "github", "logging"):
    nested = data.get(group)
    if isinstance(nested, dict):
        data.update(nested)
value = data.get(key, "")
if isinstance(value, bool):
    print("true" if value else "false")
elif value is None:
    print("")
else:
    print(value)
PY
}

shutdown_processes() {
    local status="${1:-0}"

    trap - TERM INT EXIT

    for pid in "${ha_mcp_pid}" "${tunnel_control_pid}" "${nginx_pid}" "${mcphub_pid}"; do
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            kill -TERM "${pid}" 2>/dev/null || true
        fi
    done

    for pid in "${ha_mcp_pid}" "${tunnel_control_pid}" "${nginx_pid}" "${mcphub_pid}"; do
        if [[ -n "${pid}" ]]; then
            wait "${pid}" 2>/dev/null || true
        fi
    done

    exit "${status}"
}

# ha-mcp reaches MCPHub only on loopback and receives no App secrets. uvx
# resolves @latest at every start, so an App restart updates it.
start_ha_mcp() {
    (
        unset JWT_SECRET HA_INGRESS_PROXY_SECRET
        export MCP_HOST="127.0.0.1"
        export MCP_PORT="8096"
        export FASTMCP_SHOW_SERVER_BANNER="false"
        if [[ "${ha_mcp_auth_mode}" == "supervisor" ]]; then
            export HOMEASSISTANT_URL="http://supervisor/core"
            export HOMEASSISTANT_TOKEN="${SUPERVISOR_TOKEN:-}"
        else
            unset SUPERVISOR_TOKEN
            export HOMEASSISTANT_URL="${ha_mcp_url%/}"
            HOMEASSISTANT_TOKEN="$(option ha_mcp_user_token)"
            export HOMEASSISTANT_TOKEN
        fi
        exec uvx --from ha-mcp@latest ha-mcp-web
    ) &
    ha_mcp_pid="$!"
}

trap 'shutdown_processes 143' TERM
trap 'shutdown_processes 130' INT


home_assistant_mcp_enabled="$(option home_assistant_mcp_enabled)"
home_assistant_mcp_enabled="${home_assistant_mcp_enabled:-false}"
home_assistant_mcp_auth_mode="$(option home_assistant_mcp_auth_mode)"
home_assistant_mcp_auth_mode="${home_assistant_mcp_auth_mode:-restricted_user}"
ha_mcp_enabled="$(option ha_mcp_enabled)"
ha_mcp_auth_mode="$(option ha_mcp_auth_mode)"
ha_mcp_auth_mode="${ha_mcp_auth_mode:-supervisor}"
ha_mcp_url="$(option ha_mcp_url)"

mkdir -p     "${MCPHUB_DATA_DIR}"     "${SECRET_DIR}"     /data/home     /data/cache/npm     /data/cache/uv

chmod 0700 "${SECRET_DIR}"

/usr/local/bin/prepare_mcphub_config.py
/usr/local/bin/prepare_proxy_config.py

if [[ "${home_assistant_mcp_enabled}" == "true" ]]; then
    log_info "Managed Home Assistant MCP server enabled with ${home_assistant_mcp_auth_mode} authentication."
fi

export PORT="3000"
export BASE_PATH=""
export NODE_ENV="production"
export MCPHUB_SETTING_PATH="${MCPHUB_DATA_DIR}/mcp_settings.json"
export JWT_SECRET
JWT_SECRET="$(cat "${JWT_SECRET_FILE}")"
export HA_INGRESS_PROXY_SECRET
HA_INGRESS_PROXY_SECRET="$(cat "${HA_INGRESS_PROXY_SECRET_FILE}")"

# Persist package caches used by dynamically installed npx and uvx MCP servers.
export HOME="/data/home"
export XDG_CACHE_HOME="/data/cache"
export NPM_CONFIG_CACHE="/data/cache/npm"
export UV_CACHE_DIR="/data/cache/uv"
export UV_PYTHON_INSTALL_DIR="/data/cache/uv-python"

# Started before MCPHub so its first connection finds the server. The first
# start downloads ha-mcp; a failure here never stops MCPHub.
if [[ "${ha_mcp_enabled}" == "true" ]]; then
    log_info "Starting the unofficial Home Assistant MCP server (ha-mcp) with ${ha_mcp_auth_mode} authentication."
    start_ha_mcp
    ha_mcp_ready=false
    for _ in $(seq 1 90); do
        kill -0 "${ha_mcp_pid}" 2>/dev/null || break
        if curl --silent --output /dev/null --max-time 1 http://127.0.0.1:8096/mcp; then
            ha_mcp_ready=true
            break
        fi
        sleep 1
    done
    if [[ "${ha_mcp_ready}" != "true" ]]; then
        log_warn "ha-mcp is not ready yet; MCPHub starts without waiting for it."
    fi
fi

log_info "Starting MCPHub 1.1.15 on internal loopback port 3000."
if [[ -r /etc/mcphub-source-revision ]]; then
    log_info "Build source revision: $(cat /etc/mcphub-source-revision)"
fi
(
    cd /app
    /usr/local/bin/entrypoint.sh node dist/index.js
) &
mcphub_pid="$!"

ready=false
for _ in $(seq 1 120); do
    if ! kill -0 "${mcphub_pid}" 2>/dev/null; then
        wait "${mcphub_pid}" || true
        log_error "MCPHub exited during startup."
        exit 1
    fi

    if curl --silent --fail --max-time 1 http://127.0.0.1:3000/health >/dev/null 2>&1; then
        ready=true
        break
    fi

    sleep 0.5
done

if [[ "${ready}" != "true" ]]; then
    log_error "MCPHub did not become ready within 60 seconds."
    shutdown_processes 1
fi

if ! nginx -t; then
    log_error "Generated Nginx configuration is invalid."
    shutdown_processes 1
fi

log_info "MCPHub is ready. Starting the Home Assistant Ingress adapter on port 8099."
nginx -g 'daemon off;' &
nginx_pid="$!"

log_info "Starting the isolated tunnel controller (OpenAI tunnel, remote access status) and its dashboard."
/usr/local/bin/tunnel_control.py &
tunnel_control_pid="$!"

# Optional remote tunnels must never take MCPHub or its Ingress adapter down.
# Monitor their lifecycle independently; only core process failures stop the App.
while true; do
    if ! kill -0 "${mcphub_pid}" 2>/dev/null; then
        log_error "MCPHub exited unexpectedly."
        shutdown_processes 1
    fi
    if ! kill -0 "${nginx_pid}" 2>/dev/null; then
        log_error "The Home Assistant proxy adapter exited unexpectedly."
        shutdown_processes 1
    fi

    if [[ -n "${tunnel_control_pid}" ]] && ! kill -0 "${tunnel_control_pid}" 2>/dev/null; then
        wait "${tunnel_control_pid}" 2>/dev/null || true
        log_warn "Tunnel controller exited; restarting it, MCPHub remains available."
        /usr/local/bin/tunnel_control.py &
        tunnel_control_pid="$!"
    fi

    if [[ -n "${ha_mcp_pid}" ]] && ! kill -0 "${ha_mcp_pid}" 2>/dev/null; then
        if (( SECONDS >= ha_mcp_restart_at )); then
            wait "${ha_mcp_pid}" 2>/dev/null || true
            log_warn "ha-mcp exited; restarting it, MCPHub remains available."
            ha_mcp_restart_at=$(( SECONDS + 60 ))
            start_ha_mcp
        fi
    fi
    sleep 2 &
    wait "$!" || true
done
