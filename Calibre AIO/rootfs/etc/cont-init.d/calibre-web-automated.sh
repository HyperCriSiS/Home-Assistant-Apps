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
# (cwa-init and friends, copied from the upstream project) start. CWA's
# safety copies of processed books (/config/processed_books) are book files
# too and live in a third /share folder next to the library.
# ==============================================================================

declare library_dir
declare ingest_dir
declare processed_dir
declare network_share_mode

library_dir=$(bashio::config 'library_dir')
ingest_dir=$(bashio::config 'ingest_dir')
processed_dir=$(bashio::config 'processed_dir')
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
check_share_dir processed_dir "${processed_dir}"
nested() {
    [[ "${1%/}/" == "${2%/}/"* || "${2%/}/" == "${1%/}/"* ]]
}
# The ingest watcher scans its folder recursively, so a library inside the
# ingest folder (or the reverse) would re-import the library's own books.
if nested "${library_dir}" "${ingest_dir}"; then
    bashio::log.fatal "library_dir and ingest_dir must be different folders and must not be nested"
    exit 1
fi
# The same holds for the safety copies, and inside the library they would sit
# among Calibre's own book folders.
if nested "${processed_dir}" "${library_dir}" || nested "${processed_dir}" "${ingest_dir}"; then
    bashio::log.fatal "processed_dir must be its own folder, not inside or around library_dir or ingest_dir"
    exit 1
fi

CONFIG_TARGET="/data/config"
LIBRARY_TARGET="/share/${library_dir}"
INGEST_TARGET="/share/${ingest_dir}"
PROCESSED_TARGET="/share/${processed_dir}"

mkdir -p "${CONFIG_TARGET}" "${LIBRARY_TARGET}" "${INGEST_TARGET}" "${PROCESSED_TARGET}"
chown abc:abc "${CONFIG_TARGET}"
if ! bashio::var.true "${network_share_mode}"; then
    chown abc:abc "${LIBRARY_TARGET}" "${INGEST_TARGET}" "${PROCESSED_TARGET}"
fi

# Point CWA's processed_books at the /share folder. Copies kept in the private
# App folder by earlier versions move there once; a changed option relinks.
link_processed_books() {
    local link="$1/processed_books" target="$2"
    if [ -L "${link}" ]; then
        [[ "$(readlink "${link}")" == "${target}" ]] && return 0
        rm "${link}"
    elif [ -d "${link}" ]; then
        cp -r --preserve=timestamps "${link}/." "${target}/"
        rm -rf "${link}"
        bashio::log.info "Moved CWA's processed books to ${target}"
    fi
    ln -s "${target}" "${link}"
}
link_processed_books "${CONFIG_TARGET}" "${PROCESSED_TARGET}"
if ! bashio::var.true "${network_share_mode}"; then
    chown -R abc:abc "${PROCESSED_TARGET}"
fi
mkdir -p /data/shelfmark /data/shelfmark-staging /data/shelfmark-logs /data/shelfmark-audiobooks

# CWA marks a running post-import follow-up with cwa_ingest_batch_dirty.running
# and removes the marker when it finishes. A stop in between (cold backup,
# restart) leaves it behind, and CWA then reports an import in progress forever.
# Hand it back to the queue so CWA reruns the follow-up once, as after a failure.
requeue_interrupted_follow_up() {
    local dirty="$1/cwa_ingest_batch_dirty"
    [ -e "${dirty}.running" ] || return 0
    if [ -e "${dirty}" ]; then
        rm -f "${dirty}.running"
    else
        mv "${dirty}.running" "${dirty}"
    fi
    bashio::log.info "Requeued an interrupted CWA post-import follow-up"
}
requeue_interrupted_follow_up "${CONFIG_TARGET}"
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
bashio::log.info "Processed book copies: ${PROCESSED_TARGET} (/config/processed_books)"
bashio::log.info "App config/state: ${CONFIG_TARGET} (/config)"
bashio::log.info "Network share mode: ${network_share_mode}"
