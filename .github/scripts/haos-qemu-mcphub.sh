#!/usr/bin/env bash
# Test MCPHub in a throw-away Home Assistant OS VM on a GitHub-hosted runner.
#
# The official HAOS QEMU image is booted with KVM. MCPHub is copied into the
# image's local add-on folder before the first boot, a disposable admin is
# created through onboarding, and the App is installed, built, started,
# restarted and probed through Supervisor, Ingress and its LAN MCP port. Both
# Home Assistant MCP servers are then enabled and must list real tools.
#
# Usage: haos-qemu-mcphub.sh <MCPHub source dir> <tested commit SHA>
set -Eeuo pipefail

SOURCE_DIR="${1:?MCPHub source directory}"
SOURCE_SHA="${2:?tested commit SHA}"
: "${HAOS_VERSION:?Set HAOS_VERSION to an official Home Assistant OS release}"
[[ "${HAOS_VERSION}" =~ ^[0-9]+\.[0-9]+$ ]] || { echo "Invalid HAOS_VERSION" >&2; exit 1; }
[[ "${SOURCE_SHA}" =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid source SHA" >&2; exit 1; }

WORK="${RUNNER_TEMP:-/tmp}/haos-qemu"
IMAGE="${WORK}/haos.qcow2"
HA="http://127.0.0.1:8123"
SLUG="local_mcphub"
TOKEN=""
mkdir -p "${WORK}/data"

log() { printf '\n== %s\n' "$*"; }

cleanup() {
  if [[ -s "${WORK}/qemu.pid" ]]; then
    sudo kill "$(sudo cat "${WORK}/qemu.pid")" 2>/dev/null || true
  fi
  sudo umount "${WORK}/data" 2>/dev/null || true
  sudo qemu-nbd --disconnect /dev/nbd0 >/dev/null 2>&1 || true
}
trap cleanup EXIT

diagnose() {
  log "Diagnostics"
  console "for c in \$(docker ps -a --format '{{.Names}}' | grep mcphub); do docker logs --tail 150 \$c 2>&1; done"     "docker logs --tail 80 hassio_supervisor 2>&1"
}

console() {
  # Run shell commands in the VM through its serial console (root login has
  # no password on HAOS) and print what the console shows.
  [[ -S "${WORK}/serial.sock" ]] || return 0
  local before
  before="$(sudo stat -c %s "${WORK}/serial.log")"
  for command in "" root "$@"; do
    printf '%s\n' "${command}" | sudo socat -t 2 - "UNIX-CONNECT:${WORK}/serial.sock" >/dev/null || true
    sleep 4
  done
  sleep 6
  echo "---- VM console"
  sudo tail -c "+$((before + 1))" "${WORK}/serial.log" | grep -v "audit:" || true
  echo "----"
}
trap 'diagnose' ERR

supervisor() {
  # supervisor METHOD PATH [TIMEOUT] [JSON]: Supervisor API through Core's
  # "supervisor/api" WebSocket command, as the HA frontend calls it. The REST
  # proxy under /api/hassio only allows a few endpoints.
  TOKEN="${TOKEN}" python3 - "$1" "$2" "${3:-120}" "${4:-}" <<'PY'
import json, os, sys
from websockets.sync.client import connect

method, path, timeout = sys.argv[1].lower(), "/" + sys.argv[2], int(sys.argv[3])
extra = {"data": json.loads(sys.argv[4])} if sys.argv[4] else {}
with connect("ws://127.0.0.1:8123/api/websocket", open_timeout=30, max_size=None) as ws:
    ws.recv()
    ws.send(json.dumps({"type": "auth", "access_token": os.environ["TOKEN"]}))
    if json.loads(ws.recv()).get("type") != "auth_ok":
        sys.exit("WebSocket authentication failed")
    ws.send(json.dumps({"id": 1, "type": "supervisor/api", "endpoint": path,
                        "method": method, "timeout": timeout, **extra}))
    while True:
        message = json.loads(ws.recv(timeout=timeout + 60))
        if message.get("id") == 1:
            break
if not message.get("success"):
    sys.exit(f"{method.upper()} {path} failed: {json.dumps(message.get('error'))}")
print(json.dumps({"data": message.get("result")}))
PY
}

field() {
  python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("data", d).get(sys.argv[1]) or "")' "$1"
}

wait_started() {
  local state=""
  for _ in $(seq 1 90); do
    state="$(supervisor GET "addons/${SLUG}/info" | field state)"
    [[ "${state}" == "started" ]] && return 0
    sleep 5
  done
  echo "MCPHub did not reach the started state (last: ${state})" >&2
  return 1
}

log "Download Home Assistant OS ${HAOS_VERSION}"
curl -fsSL --retry 3 -o "${IMAGE}.xz" \
  "https://github.com/home-assistant/operating-system/releases/download/${HAOS_VERSION}/haos_ova-${HAOS_VERSION}.qcow2.xz"
xz -d "${IMAGE}.xz"

log "Copy MCPHub ${SOURCE_SHA} into the image's local add-on folder"
sudo modprobe nbd max_part=16
sudo qemu-nbd --connect=/dev/nbd0 "${IMAGE}"
sudo partprobe /dev/nbd0 || true
sleep 3
data_partition=""
for partition in /dev/nbd0p*; do
  if [[ "$(sudo blkid -s LABEL -o value "${partition}" 2>/dev/null)" == "hassos-data" ]]; then
    data_partition="${partition}"
  fi
done
[[ -n "${data_partition}" ]] || { sudo blkid /dev/nbd0p* || true; echo "No hassos-data partition" >&2; exit 1; }
sudo mount "${data_partition}" "${WORK}/data"
# Supervisor 2026.10+ keeps local Apps in apps/local (older: addons/local).
sudo ls -la "${WORK}/data/supervisor" "${WORK}/data/supervisor/apps" 2>/dev/null || true
local_apps="${WORK}/data/supervisor/addons/local"
if sudo test -d "${WORK}/data/supervisor/apps"; then
  local_apps="${WORK}/data/supervisor/apps/local"
fi
target="${local_apps}/mcphub_ci"
sudo mkdir -p "${target}"
sudo rsync -a --delete "${SOURCE_DIR%/}/" "${target}/"
printf '%s\n' "${SOURCE_SHA}" | sudo tee "${target}/.haos-source-revision" >/dev/null
sudo umount "${WORK}/data"
sudo qemu-nbd --disconnect /dev/nbd0

log "Boot Home Assistant OS"
firmware=""
for candidate in /usr/share/ovmf/OVMF.fd /usr/share/qemu/OVMF.fd; do
  [[ -r "${candidate}" ]] && firmware="${candidate}" && break
done
[[ -n "${firmware}" ]] || { echo "OVMF firmware not found" >&2; exit 1; }
sudo qemu-system-x86_64 \
  -enable-kvm -cpu host -smp 4 -m 6144 -machine q35 \
  -bios "${firmware}" \
  -drive "file=${IMAGE},if=virtio,format=qcow2" \
  -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:8123-:80,hostfwd=tcp:127.0.0.1:3001-:3001,hostfwd=tcp:127.0.0.1:4357-:4357" \
  -device virtio-net-pci,netdev=net0 \
  -display none \
  -chardev "socket,id=console,path=${WORK}/serial.sock,server=on,wait=off,logfile=${WORK}/serial.log" \
  -serial chardev:console \
  -daemonize -pidfile "${WORK}/qemu.pid"

log "Wait for Home Assistant onboarding (first boot downloads Core)"
for attempt in $(seq 1 180); do
  if curl -sf --max-time 10 "${HA}/api/onboarding" | python3 -c 'import json,sys; assert isinstance(json.load(sys.stdin), list)' 2>/dev/null; then
    break
  fi
  [[ "${attempt}" -lt 180 ]] || { echo "Home Assistant never became ready" >&2; false; }
  if (( attempt % 6 == 0 )); then
    core="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${HA}/" || true)"
    observer="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:4357/ || true)"
    onboarding="$(curl -s -o /dev/null --max-time 5 -w 'HTTP %{http_code} -> %{redirect_url}' "${HA}/api/onboarding" || true)"
    echo "$((attempt / 6)) min: Core HTTP ${core}, Observer HTTP ${observer}, onboarding: ${onboarding}"
  fi
  if (( attempt == 60 )); then
    console "ha core info" "ha jobs info" "docker ps -a" "docker logs --tail 40 homeassistant"
  fi
  sleep 10
done

log "Create a disposable admin through onboarding"
password="$(openssl rand -hex 24)"
echo "::add-mask::${password}"
client_id="${HA}/"
auth_code="$(curl -sS --fail-with-body -X POST "${HA}/api/onboarding/users" \
  -H "Content-Type: application/json" \
  -d "{\"client_id\":\"${client_id}\",\"name\":\"CI\",\"username\":\"ci\",\"password\":\"${password}\",\"language\":\"en\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["auth_code"])')"
TOKEN="$(curl -sS --fail-with-body -X POST "${HA}/auth/token" \
  -d grant_type=authorization_code -d "code=${auth_code}" --data-urlencode "client_id=${client_id}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
echo "::add-mask::${TOKEN}"

log "Wait for Supervisor and the local MCPHub App"
for attempt in $(seq 1 30); do
  reload="$(supervisor POST addons/reload 300 2>&1 || true)"
  info="$(supervisor GET "addons/${SLUG}/info" 2>&1)" && break
  if (( attempt == 3 )); then
    echo "reload: ${reload}"
    echo "info: ${info}"
    supervisor GET store/repositories | head -c 1500 || true
    echo
    console "ls -la /mnt/data/supervisor /mnt/data/supervisor/apps /mnt/data/supervisor/apps/local /mnt/data/supervisor/addons" \
      "docker logs hassio_supervisor 2>&1 | grep -i -E 'local|migrat|mcphub|invalid|error|warn' | head -40"
  fi
  [[ "${attempt}" -lt 30 ]] || { echo "Supervisor did not discover ${SLUG}" >&2; false; }
  sleep 10
done

log "Install (build) MCPHub"
supervisor POST "addons/${SLUG}/install" 3000
expected="$(sed -n 's/^version: "\(.*\)"$/\1/p' "${SOURCE_DIR%/}/config.yaml")"
installed="$(supervisor GET "addons/${SLUG}/info" | field version)"
[[ -n "${expected}" && "${installed}" == "${expected}" ]] || {
  echo "Installed version ${installed} does not match source ${expected}" >&2
  false
}

log "Start, restart and probe MCPHub"
supervisor POST "addons/${SLUG}/start" 600
wait_started
supervisor POST "addons/${SLUG}/restart" 600
wait_started

ingress_entry="$(supervisor GET "addons/${SLUG}/info" | field ingress_entry)"
[[ -n "${ingress_entry}" ]] || { echo "No Ingress entry reported" >&2; false; }
session="$(supervisor POST ingress/session | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["session"])')"
echo "::add-mask::${session}"
ok=""
for _ in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
    -b "ingress_session=${session}" "${HA}${ingress_entry}/" || true)"
  [[ "${code}" == "200" ]] && ok=1 && break
  sleep 5
done
[[ -n "${ok}" ]] || { echo "Ingress did not answer with 200 (last: ${code})" >&2; false; }

# The LAN gateway serves only /mcp and requires an MCPHub bearer key, so any
# 2xx-4xx answer proves it is up; 5xx or no answer means a broken backend.
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST \
  -H "Content-Type: application/json" -d '{}' "http://127.0.0.1:3001/mcp" || true)"
[[ "${code}" =~ ^[234][0-9][0-9]$ ]] || { echo "LAN MCP port answered ${code}" >&2; false; }
echo "Installed ${installed}, state started after restart, Ingress HTTP 200, LAN /mcp HTTP ${code}"

log "Enable Home Assistant's MCP Server integration"
flow() {
  curl -sS --fail-with-body -X POST -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" -d "$2" "${HA}/api/config/config_entries/flow$1"
}
flow_json="$(flow "" '{"handler":"mcp_server"}')"
echo "${flow_json}"
if [[ "$(field type <<<"${flow_json}")" == "form" ]]; then
  flow "/$(field flow_id <<<"${flow_json}")" '{"llm_hass_api":["assist"]}'
fi

log "Enable both Home Assistant MCP servers through Supervisor authentication"
options="$(supervisor GET "addons/${SLUG}/info" | python3 -c '
import json, sys
options = json.load(sys.stdin)["data"]["options"]
options["home_assistant"].update(home_assistant_mcp_enabled=True, home_assistant_mcp_auth_mode="supervisor")
options["ha_mcp"].update(ha_mcp_enabled=True, ha_mcp_auth_mode="supervisor")
print(json.dumps({"options": options}))')"
supervisor POST "addons/${SLUG}/options" 60 "${options}"
supervisor POST "addons/${SLUG}/restart" 600
wait_started

log "List the tools of both servers from inside the App"
probe="$(base64 -w0 "$(dirname "${BASH_SOURCE[0]}")/haos-mcp-probe.py")"
result=""
for _ in $(seq 1 30); do
  output="$(console "echo ${probe} | base64 -d | docker exec -i app_${SLUG} python3 -")"
  result="$(grep -oE 'MCP_PROBE_OK official=[0-9]+ unofficial=[0-9]+' <<<"${output}" | tail -1 || true)"
  [[ -n "${result}" ]] && break
  grep -E 'MCP_PROBE_(WAIT|ERROR) ' <<<"${output}" | grep -v 'base64' || true
  sleep 10
done
[[ -n "${result}" ]] || { echo "Home Assistant MCP servers did not list tools" >&2; false; }
echo "${result}"

log "MCPHub ${expected} (${SOURCE_SHA}) works on Home Assistant OS ${HAOS_VERSION}"
