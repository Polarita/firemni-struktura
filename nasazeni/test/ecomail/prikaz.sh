#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
exec systemd-run --quiet --pipe --wait --collect -p User=pol-ecomail-test -p UMask=0077 \
    -p PrivateNetwork=yes -p RestrictAddressFamilies=AF_UNIX -p PrivateDevices=yes -p NoNewPrivileges=yes \
    -p ProtectHome=yes -p ProtectSystem=strict -p InaccessiblePaths=/srv \
    -p BindPaths=/srv/polarita/workspace/ecomail-test:/var/lib/polarita-ecomail-data \
    -p ReadWritePaths=/var/lib/polarita-ecomail-data /usr/bin/python3 -I /opt/polarita-ecomail-test/retence.py "$@"
