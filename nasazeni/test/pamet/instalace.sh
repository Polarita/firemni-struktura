#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
exec 9>/run/polarita-znalosti.lock
flock 9
if ! command -v git >/dev/null || ! command -v setfacl >/dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git acl
fi
python3 "$(dirname "$0")/znalosti.py"
