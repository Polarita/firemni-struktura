#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
root=$(readlink -e /opt/polarita-ads-mcp-test/current)
[[ $root =~ ^/opt/polarita-ads-mcp-test/[0-9a-f]{64}$ ]]
program=("$root/sdk/bin/python" -I "$root/server.py")
if [[ ${1:-} == --zkouska && $# == 1 ]]; then
    program=("$root/sdk/bin/python" -I "$root/zkouska.py" "$root/server.py")
elif [[ $# != 0 ]]; then exit 2; fi
exec systemd-run --quiet --pipe --collect --wait --service-type=exec \
    -p User=pol-ads-test -p Group=pol-ads-test -p UMask=0077 \
    -p PrivateNetwork=yes -p RestrictAddressFamilies=AF_UNIX -p NoNewPrivileges=yes \
    -p ProtectHome=yes -p PrivateTmp=yes -p PrivateDevices=yes -p ProtectSystem=strict \
    -p InaccessiblePaths=/srv -p BindPaths=/srv/polarita/workspace/reklama-test:/var/lib/polarita-ads-test \
    -p ReadWritePaths=/var/lib/polarita-ads-test -p CapabilityBoundingSet= \
    -E POLARITA_ADS_TEST_STATE=/var/lib/polarita-ads-test "${program[@]}"
