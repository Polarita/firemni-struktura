#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
image=umami-software/umami@sha256:27775432b252a187bd1e39c2e4e5e686ca71742f5fa08943ee2d18a1850ffc59
alias=polarita-umami-3.5.0
exec 9>/run/polarita-umami-obraz.lock
flock 9
if ! incus image info "$alias" >/dev/null 2>&1; then
    exec 8>/run/polarita-test-zatez.lock
    flock 8
    incus image copy "ghcr:$image" local: --alias "$alias"
fi
[[ $(incus image get-property "$alias" id) == "$image" ]]
printf 'Umami 3.5.0 pro linux/amd64 je v místním úložišti obrazů Incusu.\n'
