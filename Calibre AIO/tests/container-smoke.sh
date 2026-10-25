#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/cwa-venv/bin:$PATH"
export CALIBRE_DBPATH=/config
mkdir -p /data/config /data/shelfmark /data/shelfmark-staging /data/shelfmark-logs /data/shelfmark-audiobooks
mkdir -p /share/calibre-aio/library /share/calibre-aio/ingest
chown abc:abc /data/config /data/shelfmark /data/shelfmark-staging /data/shelfmark-logs /data/shelfmark-audiobooks
chown abc:abc /share/calibre-aio/library /share/calibre-aio/ingest
if [[ -d /config && ! -L /config ]]; then rmdir /config; fi
[[ -L /config ]] || ln -s /data/config /config
ln -sfn /share/calibre-aio/library /calibre-library
ln -sfn /share/calibre-aio/ingest /cwa-book-ingest
printf '%s\n' '{"sso":{"enabled":true,"admin_username":"ha_admin","auto_create_users":true}}' > /data/options.json
chmod 600 /data/options.json
python3 /opt/ha-cwa/prepare_aio.py /api/hassio_ingress/aio-test
timeout 180 bash /etc/s6-overlay/s6-rc.d/cwa-init/run
timeout 180 bash /etc/s6-overlay/s6-rc.d/calibre-binaries-setup/run
bash /etc/s6-overlay/s6-rc.d/cwa-auto-library/run
chown -R abc:abc /data/config /data/shelfmark
chown root:root /data/options.json
chmod 600 /data/options.json
python3 /opt/ha-cwa/launch.py &
cwa_pid=$!
bash /etc/s6-overlay/s6-rc.d/svc-shelfmark/run &
shelfmark_pid=$!
# Simulate Supervisor on a loopback alias only in this disposable smoke test.
# test_nginx.py separately tests the production 172.30.32.2 ACL unchanged.
sed -i 's/allow 172.30.32.2;/allow 127.0.0.2;/' /etc/nginx/cwa-ingress.conf
nginx -g 'daemon off;' -c /etc/nginx/cwa-ingress.conf &
nginx_pid=$!
trap 'kill "$cwa_pid" "$shelfmark_pid" "$nginx_pid" 2>/dev/null || true' EXIT
python3 /aio-tests/probe_container.py
/command/s6-setuidgid abc env 'AIO_SSO_OPTIONS={"enabled":true}' \
  /app/shelfmark/.venv/bin/python /aio-tests/probe_socket_auth.py
/command/s6-setuidgid abc env 'AIO_SSO_OPTIONS={"enabled":true}' \
  /app/shelfmark/.venv/bin/python /aio-tests/probe_delivery.py
timeout 90 python3 /app/calibre-web-automated/scripts/ingest_processor.py \
  "$(cat /data/shelfmark-staging/probe-delivery-path)"
python3 - <<'PY'
import sqlite3
with sqlite3.connect('/calibre-library/metadata.db') as db:
    assert db.execute('SELECT id FROM books WHERE title = ?',
                      ('Calibre AIO Smoke Book',)).fetchone(), 'Generated ebook was not imported'
print('Real CWA ingest imported the Shelfmark-delivered EPUB into the library')
PY
