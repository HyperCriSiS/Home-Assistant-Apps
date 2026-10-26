#!/usr/bin/env bash
set -euo pipefail
container=plextraktsync-smoke
volume=plextraktsync-smoke-data
trap 'docker rm -f "$container" >/dev/null 2>&1 || true; docker volume rm "$volume" >/dev/null 2>&1 || true' EXIT
docker volume create "$volume"
docker run --rm --user 0 --entrypoint sh -v "$volume:/data" plextraktsync:test -c \
  'cp /app/default-options.json /data/options.json'
docker run -d --name "$container" -v "$volume:/data" plextraktsync:test
for attempt in $(seq 1 30); do
  if docker exec "$container" python -c 'import socket; socket.create_connection(("127.0.0.1",8099),2).close()'; then
    break
  fi
  sleep 2
done
docker exec "$container" python -c 'import urllib.request, urllib.error
try:
    urllib.request.urlopen("http://127.0.0.1:8099/api/status")
    raise AssertionError("Direct access unexpectedly allowed")
except urllib.error.HTTPError as e:
    assert e.code == 403'
docker exec --user 1000 "$container" python -c \
  'from pathlib import Path; Path("/data/pts/persistence-test").write_text("retained")'
docker exec --user 1000 "$container" python -c 'from server import Controller
c = Controller("/data/pts")
assert c.options["sync_interval_minutes"] == 60
c.action("settings", {"revision": c.identity(), "options": {**c.options, "sync_interval_minutes": 75},
                      "credentials": {"plex_token": "nonfunctional-fixture-token"}})'
docker stop --time 30 "$container"
test "$(docker inspect -f '{{.State.ExitCode}}' "$container")" = 0
docker start "$container"
for attempt in $(seq 1 30); do
  if docker exec "$container" python -c 'import socket; socket.create_connection(("127.0.0.1",8099),2).close()'; then
    break
  fi
  sleep 2
done
docker exec "$container" python -c \
  'from pathlib import Path; assert Path("/data/pts/persistence-test").read_text() == "retained"'
docker exec --user 1000 "$container" python -c 'from server import Controller
c = Controller("/data/pts")
assert c.options["sync_interval_minutes"] == 75, "Startup overwrote Ingress settings"
assert c.credentials()["plex_token"] == "nonfunctional-fixture-token"
assert not c.approved()'
docker stop --time 30 "$container"
test "$(docker inspect -f '{{.State.ExitCode}}' "$container")" = 0
