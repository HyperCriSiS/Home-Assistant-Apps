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
# too and live in a third /share folder next to the library, and Shelfmark's
# audiobooks in a fourth.
# ==============================================================================

declare library_dir
declare ingest_dir
declare processed_dir
declare audiobook_dir
declare network_share_mode

library_dir=$(bashio::config 'library_dir')
ingest_dir=$(bashio::config 'ingest_dir')
processed_dir=$(bashio::config 'processed_dir')
audiobook_dir=$(bashio::config 'audiobook_dir')
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
check_share_dir audiobook_dir "${audiobook_dir}"
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
# among Calibre's own book folders. An update adds the default processed_dir to
# existing options, which may collide with a custom library_dir; keep booting
# and leave the copies where they are until the option is changed.
processed_link=true
if nested "${processed_dir}" "${library_dir}" || nested "${processed_dir}" "${ingest_dir}"; then
    bashio::log.warning "processed_dir must be its own folder, not inside or around library_dir or ingest_dir;" \
        "CWA's processed books stay in the private App folder, outside App backups, until it is changed"
    processed_link=false
fi
# Audiobooks inside the ingest folder would be picked up by CWA's watcher; an
# update adds the default, so a collision only warns, like processed_dir.
audiobook_link=true
if nested "${audiobook_dir}" "${library_dir}" || nested "${audiobook_dir}" "${ingest_dir}" \
    || nested "${audiobook_dir}" "${processed_dir}"; then
    bashio::log.warning "audiobook_dir must be its own folder, not inside or around library_dir, ingest_dir or processed_dir;" \
        "Shelfmark's audiobooks stay in the private App folder until it is changed"
    audiobook_link=false
fi

CONFIG_TARGET="/data/config"
LIBRARY_TARGET="/share/${library_dir}"
INGEST_TARGET="/share/${ingest_dir}"
PROCESSED_TARGET="/share/${processed_dir}"
AUDIOBOOK_TARGET="/share/${audiobook_dir}"

mkdir -p "${CONFIG_TARGET}" "${LIBRARY_TARGET}" "${INGEST_TARGET}"
chown abc:abc "${CONFIG_TARGET}"
if ! bashio::var.true "${network_share_mode}"; then
    chown abc:abc "${LIBRARY_TARGET}" "${INGEST_TARGET}"
fi

# Point a private App folder (CWA's processed_books, Shelfmark's audiobooks) at
# its /share folder. Files kept in the private App folder by earlier versions
# move there once, without overwriting files already in the target; a changed
# option relinks. The private folder is removed only when every file in it has
# an identical copy in the target, so a failed or interrupted copy (full disk,
# restart) or a file of the same name already in the target keeps it in place
# and the App bootable. Ownership is fixed only after a move.
link_share_dir() {
    local link="$1" target="$2" owner="$3" what="$4"
    mkdir -p "${target}"
    [ -n "${owner}" ] && chown "${owner}" "${target}"
    if [ -L "${link}" ]; then
        [[ "$(readlink "${link}")" == "${target}" ]] && return 0
        rm "${link}"
    elif [ -d "${link}" ]; then
        if ! cp -r --update=none --preserve=timestamps "${link}/." "${target}/" \
            || [ -n "$(cd "${link}" && find . -type f ! -exec cmp -s {} "${target}/{}" \; -print -quit)" ]; then
            bashio::log.warning "Could not move ${what} to ${target} completely; they stay in the private App folder"
            return 0
        fi
        [ -n "${owner}" ] && chown -R "${owner}" "${target}"
        rm -rf "${link}"
        bashio::log.info "Moved ${what} to ${target}"
    fi
    ln -s "${target}" "${link}"
}
owner=abc:abc
bashio::var.true "${network_share_mode}" && owner=""
if [[ "${processed_link}" == true ]]; then
    link_share_dir "${CONFIG_TARGET}/processed_books" "${PROCESSED_TARGET}" "${owner}" "CWA's processed books"
fi
mkdir -p /data/shelfmark /data/shelfmark-staging /data/shelfmark-logs
if [[ "${audiobook_link}" == true ]]; then
    link_share_dir /data/shelfmark-audiobooks "${AUDIOBOOK_TARGET}" "${owner}" "Shelfmark's audiobooks"
else
    # A link left by an earlier start would keep Shelfmark writing into /share.
    [ -L /data/shelfmark-audiobooks ] && rm /data/shelfmark-audiobooks
    mkdir -p /data/shelfmark-audiobooks
fi

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
chown abc:abc /data/shelfmark /data/shelfmark-staging /data/shelfmark-logs
[[ "${audiobook_link}" == true ]] || chown abc:abc /data/shelfmark-audiobooks

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
bashio::log.info "Shelfmark audiobooks: ${AUDIOBOOK_TARGET} (/data/shelfmark-audiobooks)"
bashio::log.info "App config/state: ${CONFIG_TARGET} (/config)"
bashio::log.info "Network share mode: ${network_share_mode}"
