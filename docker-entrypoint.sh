#!/bin/sh
set -eu

mkdir -p /app/media

if [ "$(id -u)" -eq 0 ]; then
    chown app:app /app/media
    exec runuser -u app -- "$@"
fi

exec "$@"
