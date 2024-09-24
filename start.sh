#!/bin/bash
set -euo pipefail

PUID=${PUID:-99}
PGID=${PGID:-100}

groupmod -o -g "$PGID" runner
usermod -o -u "$PUID" runner

chown -R runner:runner /app

UMASK=${UMASK:-002}

umask "$UMASK"

echo "UID: ${PUID}"
echo "GID: ${PGID}"
echo "umask: ${UMASK}"

#if [ ! -f /app/config/config.yaml ]; then
#  cp /app/config.yaml /app/config/config.yaml
#fi

/usr/bin/supervisord -c /app/supervisord.conf

