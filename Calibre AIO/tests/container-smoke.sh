#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/cwa-venv/bin:$PATH"
export CALIBRE_DBPATH=/config
mkdir -p /data/config /data/shelfmark /data/shelfmark-staging /data/shelfmark-logs
mkdir -p /share/calibre-aio/library /share/calibre-aio/ingest
if [[ -d /config && ! -L /config ]]; then rmdir /config; fi
[[ -L /config ]] || ln -s /data/config /config
ln -sfn /share/calibre-aio/library /calibre-library
ln -sfn /share/calibre-aio/ingest /cwa-book-ingest
printf '%s\n' '{"sso":{"enabled":true,"auto_create_users":true}}' > /data/options.json
chmod 600 /data/options.json
python3 /opt/ha-cwa/prepare_aio.py /api/hassio_ingress/aio-test
bash /etc/s6-overlay/s6-rc.d/cwa-init/run
bash /etc/s6-overlay/s6-rc.d/cwa-auto-library/run
chown -R abc:abc /data
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
