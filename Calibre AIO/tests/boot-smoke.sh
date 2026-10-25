#!/usr/bin/env bash
# Run on a disposable CI Docker host, with the freshly built image loaded.
set -euo pipefail
tests="$(cd "$(dirname "$0")" && pwd)"
cleanup() {
    result=$?
    if [[ "$result" -ne 0 ]]; then
        docker logs calibre-aio-boot || true
        docker logs calibre-aio-supervisor || true
    fi
    docker rm -f calibre-aio-boot calibre-aio-supervisor >/dev/null 2>&1 || true
    docker network rm calibre-aio-boot-net >/dev/null 2>&1 || true
    docker volume rm calibre-aio-boot-data calibre-aio-boot-share >/dev/null 2>&1 || true
    exit "$result"
}
trap cleanup EXIT
docker network create --subnet 172.30.32.0/24 calibre-aio-boot-net
docker volume create calibre-aio-boot-data
docker volume create calibre-aio-boot-share
docker run --rm --entrypoint bash -v calibre-aio-boot-data:/data \
    -v "$tests:/aio-tests:ro" calibre-aio:test -c \
    'cp /aio-tests/boot-options.json /data/options.json; chmod 600 /data/options.json'
docker run -d --name calibre-aio-supervisor --network calibre-aio-boot-net \
    --network-alias supervisor --ip 172.30.32.2 --entrypoint python3 \
    -v "$tests:/aio-tests:ro" calibre-aio:test /aio-tests/fake_supervisor.py
docker run -d --name calibre-aio-boot --network calibre-aio-boot-net --ip 172.30.32.3 \
    -e SUPERVISOR_TOKEN=ci-fixture-only \
    -v calibre-aio-boot-data:/data -v calibre-aio-boot-share:/share \
    -v "$tests:/aio-tests:ro" calibre-aio:test
probe() {
    docker exec -e AIO_PROBE_HOST=calibre-aio-boot calibre-aio-supervisor \
        python3 /aio-tests/probe_container.py
    docker exec calibre-aio-boot python3 -c \
        'import urllib.request, urllib.error
try:
    urllib.request.urlopen("http://127.0.0.1:8084/")
except urllib.error.HTTPError as error:
    assert error.code == 403
else:
    raise AssertionError("Non-Supervisor peer was accepted")'
    docker exec calibre-aio-boot test -L /config
    docker exec calibre-aio-boot test -f /data/config/app.db
    docker exec calibre-aio-boot test -f /calibre-library/metadata.db
}
probe
docker exec calibre-aio-boot sh -c 'printf persistent > /data/config/boot-probe'
docker restart calibre-aio-boot
probe
docker exec calibre-aio-boot grep -qx persistent /data/config/boot-probe

# A default installation must boot safely, rather than loop on an empty admin.
docker exec calibre-aio-boot python3 -c \
    'import json; p="/data/options.json"; d=json.load(open(p)); d["sso"]["admin_username"]=""; open(p,"w").write(json.dumps(d))'
docker restart calibre-aio-boot
docker exec calibre-aio-supervisor python3 -c \
    'import json,time,urllib.request,urllib.error
for attempt in range(120):
    try:
        root=urllib.request.urlopen("http://calibre-aio-boot:8084/").read()
        request=urllib.request.Request("http://calibre-aio-boot:8084/shelfmark/api/auth/check",headers={"X-Remote-User-Id":"a"*32,"X-Remote-User-Name":"ha_admin","X-Remote-User-Groups":"system-admin"})
        auth=json.load(urllib.request.urlopen(request))
        assert b"data-setup-required=\"true\"" in root
        assert b"src=\"about:blank\"" in root
        assert auth["is_admin"] is False
        break
    except (OSError,AssertionError): time.sleep(1)
else: raise AssertionError("Empty-admin setup did not become ready")'
echo 'Real /init first boot and restart passed with persistent storage and production ingress ACL'
