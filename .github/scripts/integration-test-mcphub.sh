#!/usr/bin/env bash
set -Eeuo pipefail

IMAGE="${1:-mcphub-addon:test}"
NETWORK="mcphub-ci-${RANDOM}"
CONTAINER="mcphub-addon-test-${RANDOM}"
VOLUME="mcphub-data-${RANDOM}"
INGRESS_IMAGE="curlimages/curl:8.16.0"
INGRESS_PATH="/api/hassio_ingress/mcphub-test"

cleanup() {
  docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
  docker volume rm "${VOLUME}" >/dev/null 2>&1 || true
  docker network rm "${NETWORK}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create --subnet 172.30.32.0/24 "${NETWORK}" >/dev/null
docker volume create "${VOLUME}" >/dev/null

write_options() {
  docker run --rm \
    --volume "${VOLUME}:/data" \
    alpine:3.22 \
    sh -c 'cat > /data/options.json <<EOF
{"home_assistant_mcp_enabled":false,"home_assistant_mcp_auth_mode":"restricted_user","home_assistant_mcp_user_token":"","home_assistant_mcp_url":"http://homeassistant:8123/api/mcp","tunnel_enabled":false,"openai_runtime_api_key":"","tunnel_id":"","tunnel_mcp_path":"/mcp","tunnel_log_level":"info"}
EOF'
}

start_addon() {
  docker run -d \
    --name "${CONTAINER}" \
    --network "${NETWORK}" \
    --ip 172.30.32.3 \
    --publish "127.0.0.1::3001/tcp" \
    --volume "${VOLUME}:/data" \
    "${IMAGE}" >/dev/null
}

wait_ready() {
  for _ in $(seq 1 120); do
    if docker exec "${CONTAINER}" curl --silent --fail --max-time 1 \
      http://127.0.0.1:3000/health >/dev/null 2>&1; then
      return 0
    fi

    if [[ "$(docker inspect -f '{{.State.Running}}' "${CONTAINER}")" != "true" ]]; then
      docker logs "${CONTAINER}" || true
      echo "MCPHub test container exited during startup" >&2
      return 1
    fi

    sleep 1
  done

  docker logs "${CONTAINER}" || true
  echo "MCPHub did not become ready" >&2
  return 1
}

ingress_curl() {
  docker run --rm \
    --network "${NETWORK}" \
    --ip 172.30.32.2 \
    "${INGRESS_IMAGE}" \
    --header "X-Remote-User-Id: test-user-id" \
    --header "X-Remote-User-Name: test-admin" \
    --header "X-Remote-User-Display-Name: Test Admin" \
    "$@"
}

ingress_curl_without_identity() {
  docker run --rm \
    --network "${NETWORK}" \
    --ip 172.30.32.2 \
    "${INGRESS_IMAGE}" \
    "$@"
}

write_options
start_addon
wait_ready

# Exercise the LAN MCP gateway through a real Docker host-port mapping.
# It must serve only MCP routes; MCPHub's web interface stays Ingress-only.
lan_binding="$(docker port "${CONTAINER}" 3001/tcp)"
[[ "${lan_binding}" == 127.0.0.1:* ]] || {
  echo "LAN proxy was not mapped to host loopback" >&2
  exit 1
}
lan_port="${lan_binding##*:}"
# MCPHub's core /health becomes available before nginx finishes startup.
lan_ready=false
for _ in $(seq 1 25); do
  if curl --fail --silent --max-time 2 "http://127.0.0.1:${lan_port}/health" >/dev/null 2>&1; then
    lan_ready=true
    break
  fi
  sleep 1
done
[[ "${lan_ready}" == "true" ]] || {
  docker logs "${CONTAINER}" || true
  echo "LAN proxy was not reachable after nginx startup" >&2
  exit 1
}

# A LAN client MUST NOT be able to impersonate a Home Assistant Ingress admin.
if curl --fail --silent --max-time 5   --header "X-MCPHub-HA-Proxy-Secret: fake-secret"   --header "X-Remote-User-Id: injected"   --header "X-Remote-User-Name: injected-admin"   --header "X-Remote-User-Display-Name: Injected Admin"   "http://127.0.0.1:${lan_port}/api/servers" >/dev/null 2>&1; then
  echo "LAN proxy accepted forged Home Assistant credentials" >&2
  exit 1
fi

# Also reject forged identities on MCPHub's current-user endpoint.
lan_user="$(curl --silent --show-error --max-time 5   --header "X-MCPHub-HA-Proxy-Secret: fake-secret"   --header "X-Remote-User-Id: injected"   --header "X-Remote-User-Name: injected-admin"   "http://127.0.0.1:${lan_port}/api/better-auth/user")"
python3 - "${lan_user}" <<'PYLAN'
import json
import sys
try:
    value = json.loads(sys.argv[1])
except ValueError:
    value = {}
assert value.get("success") is not True, value
assert value.get("user", {}).get("isAdmin") is not True, value
PYLAN

# MCP requests without a bearer key must remain protected by MCPHub.
no_key_code="$(curl --silent --output /dev/null --write-out '%{http_code}'   --max-time 5 --request POST   --header 'Content-Type: application/json'   --header 'Accept: application/json, text/event-stream'   --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"lan-ci","version":"1.0"}}}'   "http://127.0.0.1:${lan_port}/mcp")"
[[ "${no_key_code}" == "401" || "${no_key_code}" == "403" ]] || {
  echo "LAN MCP endpoint failed to reject missing bearer key (HTTP ${no_key_code})" >&2
  exit 1
}

# The LAN gateway must not serve the web interface, login or management API,
# including raw dot-segment paths that normalize to an MCP route.
for path in / /login /api/servers /api/better-auth/user /api/settings \
    /_mcphub_tunnels/ /_mcphub_tunnels/api/status /sse /messages \
    /api/../mcp /mcp/../api/servers /mcp/%2e%2e/api/servers; do
  lan_code="$(curl --silent --path-as-is --output /dev/null --write-out '%{http_code}' \
    --max-time 5 "http://127.0.0.1:${lan_port}${path}")"
  if [[ "${path}" == "/api/../mcp" ]]; then
    # Normalizes to /mcp: MCPHub must still demand a bearer key.
    [[ "${lan_code}" == "401" || "${lan_code}" == "403" || "${lan_code}" == "405" ]] || {
      echo "LAN gateway mishandled ${path} (HTTP ${lan_code})" >&2
      exit 1
    }
  elif [[ "${lan_code}" != "404" && "${lan_code}" != "400" ]]; then
    echo "LAN gateway exposed ${path} (HTTP ${lan_code})" >&2
    exit 1
  fi
done

# The tunnel controller (OpenAI tunnel, remote access status) and its
# dashboard must be reachable only through HA Ingress, without exposing a
# separate unauthenticated port or requiring a running tunnel.
for _ in $(seq 1 20); do
  if ingress_curl --fail --silent \
    "http://${CONTAINER}:8099/_mcphub_tunnels/api/status" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

manager_status="$(ingress_curl --fail --silent --show-error \
  "http://${CONTAINER}:8099/_mcphub_tunnels/api/status")"
python3 - "${manager_status}" <<'PYTEST'
import json
import sys
status = json.loads(sys.argv[1])
openai = status['openai']
assert openai['state'] == 'stopped', openai
assert not openai['process_alive'], openai
assert openai['configured'] is False, openai
assert set(status) == {'openai', 'remote'}, status
remote = status['remote']
assert remote['external_url'] == '', remote
assert remote['check'] is None, remote
# CI has no Supervisor: App states must say unknown, never "not installed".
assert remote['supervisor_available'] is False, remote
for app in remote['apps'].values():
    assert app['state'] == 'unknown', remote
    assert app['link'].startswith('https://my.home-assistant.io/'), remote
assert 'openai_runtime_api_key' not in json.dumps(status), status
PYTEST

# The legacy OpenAI-only control location is gone and must not reach any API.
legacy_body="$(ingress_curl --silent --max-time 5 \
  "http://${CONTAINER}:8099/_mcphub_tunnel/api/status" || true)"
if grep -q '"process_alive"' <<<"${legacy_body}"; then
  echo 'Legacy /_mcphub_tunnel/ control location is still served' >&2
  exit 1
fi

dashboard_html="$(ingress_curl --fail --silent --show-error \
  "http://${CONTAINER}:8099/_mcphub_tunnels/")"
grep -q 'id="t-openai"' <<<"${dashboard_html}"
grep -q 'id="t-remote"' <<<"${dashboard_html}"
grep -q 'Show logs' <<<"${dashboard_html}"
if grep -q 'id="t-cloudflare"\|id="t-tailscale"' <<<"${dashboard_html}"; then
  echo 'Removed Cloudflare/Tailscale cards are still rendered' >&2
  exit 1
fi
for removed in api/logs/cloudflare api/diagnostics/tailscale api/client-key api/tailscale/gate; do
  removed_code="$(ingress_curl --silent --output /dev/null --write-out '%{http_code}' \
    --header 'X-MCPHub-Tunnel-Control: 1' \
    "http://${CONTAINER}:8099/_mcphub_tunnels/${removed}")"
  [[ "${removed_code}" == "404" ]] || {
    echo "Removed endpoint ${removed} answered HTTP ${removed_code}" >&2
    exit 1
  }
done

# Only the OpenAI tunnel is a managed process with logs and diagnostics.
mode=openai
logs="$(ingress_curl --fail --silent --show-error \
  "http://${CONTAINER}:8099/_mcphub_tunnels/api/logs/${mode}")"
python3 - "${logs}" <<'PYLOG'
import json
import sys
value = json.loads(sys.argv[1])
assert isinstance(value["lines"], list), value
assert value.get("limited") is True, value
PYLOG
details="$(ingress_curl --fail --silent --show-error \
  "http://${CONTAINER}:8099/_mcphub_tunnels/api/diagnostics/${mode}")"
python3 - "${details}" <<'PYDETAIL'
import json
import sys
assert isinstance(json.loads(sys.argv[1]), dict)
PYDETAIL

# MCPHub's Ingress frontend links to the tunnel console via a small script.
frontend_html="$(ingress_curl --fail --silent --show-error \
  --header "X-Ingress-Path: ${INGRESS_PATH}" \
  "http://${CONTAINER}:8099/")"
grep -q 'mcphub-ha-nav.js' <<<"${frontend_html}" || {
  echo "MCPHub frontend is missing the Ingress tunnel link" >&2
  exit 1
}
nav_script="$(ingress_curl --fail --silent --show-error \
  "http://${CONTAINER}:8099/mcphub-ha-nav.js")"
grep -q '_mcphub_tunnels/' <<<"${nav_script}" || {
  echo "MCPHub tunnel link script was not served through Ingress" >&2
  exit 1
}

# The address check refuses to run without a configured external address.
check_code="$(ingress_curl --silent --output /dev/null --write-out '%{http_code}' \
  -H 'X-MCPHub-Tunnel-Control: 1' \
  "http://${CONTAINER}:8099/_mcphub_tunnels/api/remote/check")"
[[ "${check_code}" == "409" ]] || {
  echo "Address check without an external address answered HTTP ${check_code}" >&2
  exit 1
}

# The MCP gateway marks its responses so the address check can recognise it.
marker="$(curl --silent --output /dev/null --dump-header - --max-time 5 \
  "http://127.0.0.1:${lan_port}/mcp" | tr -d '\r' | grep -i '^x-mcphub-gateway:' || true)"
[[ "${marker,,}" == "x-mcphub-gateway: mcp-only" ]] || {
  echo "MCP gateway response is missing its marker header (${marker})" >&2
  exit 1
}

# Native LAN cannot reach the privileged Ingress tunnel API.
lan_admin="$(curl --silent --show-error --max-time 5 \
  "http://127.0.0.1:${lan_port}/_mcphub_tunnels/api/status")"
if python3 - "${lan_admin}" <<'PYLANADMIN'
import json
import sys
try:
    payload = json.loads(sys.argv[1])
except ValueError:
    raise SystemExit(1)
raise SystemExit(0 if 'openai' in payload and 'remote' in payload else 1)
PYLANADMIN
then
  echo 'LAN unexpectedly exposed tunnel administration JSON' >&2
  exit 1
fi

# Browser form-like cross-origin requests must not be able to mutate the tunnel.
response_code="$(ingress_curl --silent --output /dev/null --write-out '%{http_code}' \
  --request POST --header 'Content-Type: application/json' --data '{}' \
  "http://${CONTAINER}:8099/_mcphub_tunnels/api/control/openai/start")"
[[ "${response_code}" == "403" ]] || { echo 'Tunnel control accepted unauthenticated POST' >&2; exit 1; }

# Even a requested start with incomplete credentials must not shut down MCPHub.
ingress_curl --fail --silent --show-error \
  --request POST --header 'Content-Type: application/json' \
  --header 'X-MCPHub-Tunnel-Control: 1' --data '{}' \
  "http://${CONTAINER}:8099/_mcphub_tunnels/api/control/openai/start" >/dev/null
docker exec "${CONTAINER}" curl --fail --silent --max-time 3 \
  http://127.0.0.1:3000/health >/dev/null

config_json="$(ingress_curl --fail --silent --show-error \
  --header "X-Ingress-Path: ${INGRESS_PATH}" \
  "http://${CONTAINER}:8099/config")"

python3 - "${config_json}" "${INGRESS_PATH}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
expected = sys.argv[2]
actual = payload.get("data", {}).get("basePath")
if actual != expected:
    raise SystemExit(f"Unexpected Ingress basePath: {actual!r}, expected {expected!r}")
PY

ingress_curl --fail --silent --show-error \
  --header "X-Ingress-Path: ${INGRESS_PATH}" \
  "http://${CONTAINER}:8099/" >/dev/null

user_json="$(ingress_curl --fail --silent --show-error \
  --header "X-Ingress-Path: ${INGRESS_PATH}" \
  "http://${CONTAINER}:8099/api/better-auth/user")"

python3 - "${user_json}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
user = payload.get("user", {})
if payload.get("success") is not True:
    raise SystemExit("Home Assistant SSO user endpoint did not succeed")
if user.get("username") != "test-admin":
    raise SystemExit(f"Unexpected Home Assistant SSO username: {user.get('username')!r}")
if user.get("isAdmin") is not True:
    raise SystemExit("Home Assistant Ingress user was not mapped to MCPHub admin")
PY

fallback_user_json="$(ingress_curl_without_identity --fail --silent --show-error \
  --header "X-Ingress-Path: ${INGRESS_PATH}" \
  "http://${CONTAINER}:8099/api/better-auth/user")"

python3 - "${fallback_user_json}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
user = payload.get("user", {})
if payload.get("success") is not True:
    raise SystemExit("Trusted Home Assistant Ingress fallback did not authenticate")
if user.get("username") != "homeassistant-admin":
    raise SystemExit(f"Unexpected fallback username: {user.get('username')!r}")
if user.get("isAdmin") is not True:
    raise SystemExit("Trusted Home Assistant Ingress fallback was not mapped to admin")
PY

if docker exec "${CONTAINER}" curl --fail --silent --max-time 2 \
  --header "X-Remote-User-Id: spoofed-user" \
  --header "X-Remote-User-Name: spoofed-admin" \
  http://127.0.0.1:3000/api/servers >/dev/null 2>&1; then
  echo "MCPHub trusted Home Assistant identity headers without the private proxy secret" >&2
  exit 1
fi

if docker run --rm \
  --network "${NETWORK}" \
  --ip 172.30.32.4 \
  "${INGRESS_IMAGE}" \
  --fail --silent --max-time 2 \
  "http://${CONTAINER}:8099/health" >/dev/null 2>&1; then
  echo "Ingress adapter accepted a non-Supervisor source address" >&2
  exit 1
fi

if docker run --rm \
  --network "${NETWORK}" \
  --ip 172.30.32.5 \
  "${INGRESS_IMAGE}" \
  --fail --silent --max-time 2 \
  "http://${CONTAINER}:3000/health" >/dev/null 2>&1; then
  echo "MCPHub port 3000 is reachable from another container" >&2
  exit 1
fi

token_before="$(docker exec "${CONTAINER}" cat /data/secrets/mcphub_tunnel_token)"
[[ -n "${token_before}" ]]

if docker exec "${CONTAINER}" grep -q '"ha-home-assistant"' /data/mcphub/mcp_settings.json; then
  echo "Managed Home Assistant MCP server exists while the option is disabled" >&2
  exit 1
fi

docker rm -f "${CONTAINER}" >/dev/null
start_addon
wait_ready

token_after="$(docker exec "${CONTAINER}" cat /data/secrets/mcphub_tunnel_token)"
[[ "${token_before}" == "${token_after}" ]] || {
  echo "Persistent internal bearer token changed after restart" >&2
  exit 1
}


# An external address is handed to MCPHub as its install base URL and can be
# checked end to end. Here the address is the container's own MCP gateway,
# standing in for a Cloudflare hostname or Tailscale Funnel URL.
docker rm -f "${CONTAINER}" >/dev/null
docker run --rm --volume "${VOLUME}:/data" alpine:3.22 sh -c "cat > /data/options.json <<EOF
{\"tunnel_enabled\":false,\"remote_access\":{\"external_url\":\"http://${CONTAINER}:3001\"}}
EOF"
start_addon
wait_ready
docker exec "${CONTAINER}" grep -q "\"baseUrl\": \"http://${CONTAINER}:3001\"" \
  /data/mcphub/mcp_settings.json || {
  echo "External address was not applied as MCPHub base URL" >&2
  exit 1
}
for _ in $(seq 1 20); do
  if ingress_curl --fail --silent \
    "http://${CONTAINER}:8099/_mcphub_tunnels/api/status" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
remote_check="$(ingress_curl --fail --silent --show-error \
  -H 'X-MCPHub-Tunnel-Control: 1' \
  "http://${CONTAINER}:8099/_mcphub_tunnels/api/remote/check")"
python3 - "${remote_check}" <<'PYCHECK'
import json
import sys
result = json.loads(sys.argv[1])
assert result["result"] == "reachable", result
PYCHECK

logs="$(docker logs "${CONTAINER}" 2>&1 || true)"
printf '%s\n' "${logs}"

if grep -Eiq 'uncaught exception|unhandled rejection|FATAL|migration failed|SQLITE_CORRUPT' <<<"${logs}"; then
  echo "Critical error pattern found in MCPHub logs" >&2
  exit 1
fi

printf '%s\n' "MCPHub container integration test passed"