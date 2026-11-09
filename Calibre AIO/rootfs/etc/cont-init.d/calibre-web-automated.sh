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

# Both paths must stay inside /share: an empty value would make /share itself
# the library and a dot segment would leave the persistent share.
check_share_dir() {
    local name="$1" value="$2" part parts
    if [[ -z "${value}" || "${value}" == /* || "${value}" == *//* ]]; then
        bashio::log.fatal "${name} must be a relative path below /share"
        exit 1
    fi
    IFS=/ read -r -a parts <<< "${value}"
    for part in "${parts[@]}"; do
        if [[ "${part}" == "." || "${part}" == ".." ]]; then
            bashio::log.fatal "${name} must not contain . or .. segments"
            exit 1
        fi
    done
}
check_share_dir library_dir "${library_dir}"
check_share_dir ingest_dir "${ingest_dir}"
# The ingest watcher scans its folder recursively, so a library inside the
# ingest folder (or the reverse) would re-import the library's own books.
if [[ "${library_dir%/}/" == "${ingest_dir%/}/"* || "${ingest_dir%/}/" == "${library_dir%/}/"* ]]; then
    bashio::log.fatal "library_dir and ingest_dir must be different folders and must not be nested"
    exit 1
fi

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
bashio::log.warning "The library under /share is not part of App backups; include the Share folder in HA backups or back it up separately"
bashio::log.info "Book ingest folder: ${INGEST_TARGET} (/cwa-book-ingest)"
bashio::log.info "App config/state: ${CONFIG_TARGET} (/config)"
bashio::log.info "Network share mode: ${network_share_mode}"
