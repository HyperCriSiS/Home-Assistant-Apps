#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -euo pipefail
ingress_path=$(bashio::app.ingress_entry)
if [[ -z "${ingress_path}" ]]; then
    bashio::log.fatal "Calibre AIO needs a Supervisor ingress path."
    exit 1
fi
app_slug=$(bashio::app.slug)
python3 /opt/ha-cwa/prepare_aio.py "${ingress_path}" "${app_slug}"
bashio::log.info "Calibre AIO ingress configured."
