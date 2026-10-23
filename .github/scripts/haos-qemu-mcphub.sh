#!/usr/bin/env bash
# Test MCPHub in a throw-away Home Assistant OS VM on a GitHub-hosted runner.
#
# The official HAOS QEMU image is booted with KVM. MCPHub is copied into the
# image's local add-on folder before the first boot, a disposable admin is
# created through onboarding, and the App is installed, built, started,
# restarted and probed through Supervisor, Ingress and its LAN MCP port.
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
  if [[ -n "${TOKEN}" ]]; then
    curl -sS --max-time 30 -H "Authorization: Bearer ${TOKEN}" \
      "${HA}/api/hassio/addons/${SLUG}/logs" | tail -n 200 || true
    curl -sS --max-time 30 -H "Authorization: Bearer ${TOKEN}" \
      "${HA}/api/hassio/supervisor/logs" | tail -n 120 || true
  fi
  sudo tail -n 80 "${WORK}/serial.log" 2>/dev/null || true
}
trap 'diagnose' ERR

supervisor() {
  # supervisor METHOD PATH [TIMEOUT]: Supervisor API through the Core proxy.
  curl -sS --fail-with-body --max-time "${3:-120}" -X "$1" \
    -H "Authorization: Bearer ${TOKEN}" "${HA}/api/hassio/$2"
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
target="${WORK}/data/supervisor/addons/local/mcphub_ci"
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
  -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:8123-:8123,hostfwd=tcp:127.0.0.1:3001-:3001" \
  -device virtio-net-pci,netdev=net0 \
  -display none -serial "file:${WORK}/serial.log" \
  -daemonize -pidfile "${WORK}/qemu.pid"

log "Wait for Home Assistant onboarding (first boot downloads Core)"
for attempt in $(seq 1 180); do
  if curl -sf --max-time 10 "${HA}/api/onboarding" | python3 -c 'import json,sys; assert isinstance(json.load(sys.stdin), list)' 2>/dev/null; then
    break
  fi
  [[ "${attempt}" -lt 180 ]] || { echo "Home Assistant never became ready" >&2; false; }
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
for attempt in $(seq 1 60); do
  if supervisor POST store/reload 300 >/dev/null 2>&1 \
    && supervisor GET "addons/${SLUG}/info" >/dev/null 2>&1; then
    break
  fi
  [[ "${attempt}" -lt 60 ]] || { echo "Supervisor did not discover ${SLUG}" >&2; false; }
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

log "MCPHub ${expected} (${SOURCE_SHA}) works on Home Assistant OS ${HAOS_VERSION}"
