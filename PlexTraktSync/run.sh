#!/bin/sh
set -eu
umask 077
mkdir -p /data/pts /data/cache /data/log
# Import legacy Supervisor options once. Ingress owns settings after bootstrap.
if [ ! -f /data/pts/options.json ]; then
    if [ -f /data/options.json ]; then
        cp /data/options.json /data/pts/options.json
    else
        printf '%s\n' '{}' > /data/pts/options.json
    fi
fi
chown -R 1000:1000 /data/pts /data/cache /data/log
exec s6-setuidgid pts python /app/server.py
