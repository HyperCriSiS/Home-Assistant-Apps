#!/bin/sh
set -eu
umask 077
mkdir -p /data/pts /data/cache /data/log
cp /data/options.json /data/pts/options.json
chown -R 1000:1000 /data/pts /data/cache /data/log
exec s6-setuidgid pts python /app/server.py
