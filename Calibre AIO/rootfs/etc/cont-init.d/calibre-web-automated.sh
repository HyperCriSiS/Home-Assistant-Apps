#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -euo pipefail
# ==============================================================================
# Calibre-Web Automated add-on initialization
#
# Calibre-Web Automated (CWA) hardcodes three paths: /config (its own app
# state - app.db, cwa.db, conversion tmp, etc.), /calibre-library (the
# Calibre library itself) and /cwa-book-ingest (the folder it watches for new
# books to auto-import). None of those are HA's own "config" share, so they
# are pointed at the add-on's private /data volume and at user-configurable
# subdirectories of /share instead, before CWA's own s6 services
# (cwa-init and friends, copied from the upstream project) start.
# ==============================================================================

declare library_dir
declare ingest_dir
declare network_share_mode

library_dir=$(bashio::config 'library_dir')
ingest_dir=$(bashio::config 'ingest_dir')
network_share_mode=$(bashio::config 'network_share_mode')

CONFIG_TARGET="/data/config"
LIBRARY_TARGET="/share/${library_dir}"
INGEST_TARGET="/share/${ingest_dir}"

mkdir -p "${CONFIG_TARGET}" "${LIBRARY_TARGET}" "${INGEST_TARGET}"
chown abc:abc "${CONFIG_TARGET}"
if ! bashio::var.true "${network_share_mode}"; then
    chown abc:abc "${LIBRARY_TARGET}" "${INGEST_TARGET}"
fi
mkdir -p /data/shelfmark /data/shelfmark-staging /data/shelfmark-logs /data/shelfmark-audiobooks
chown abc:abc /data/shelfmark /data/shelfmark-staging /data/shelfmark-logs /data/shelfmark-audiobooks

link_dir() {
    local target="$1"
    local link="$2"

    if [ -L "${link}" ]; then
        if [[ "$(readlink "${link}")" != "${target}" ]]; then
            bashio::log.fatal "Unexpected storage symlink: ${link}"
            exit 1
        fi
        return 0
    fi

    if [ -e "${link}" ]; then
        bashio::log.fatal "${link} must point to persistent storage; refusing container-local state."
        exit 1
    fi

    ln -s "${target}" "${link}"
}

link_dir "${CONFIG_TARGET}" "/config"
link_dir "${LIBRARY_TARGET}" "/calibre-library"
link_dir "${INGEST_TARGET}" "/cwa-book-ingest"

if bashio::var.true "${network_share_mode}"; then
    printf 'true' > /var/run/s6/container_environment/NETWORK_SHARE_MODE
else
    printf 'false' > /var/run/s6/container_environment/NETWORK_SHARE_MODE
fi

bashio::log.info "Calibre library: ${LIBRARY_TARGET} (/calibre-library)"
bashio::log.info "Book ingest folder: ${INGEST_TARGET} (/cwa-book-ingest)"
bashio::log.info "App config/state: ${CONFIG_TARGET} (/config)"
bashio::log.info "Network share mode: ${network_share_mode}"
