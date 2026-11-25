#!/bin/bash
# Spouští se jako dočasný účet v samostatné jednotce systemd.
set -euo pipefail
phase=$1
rev=$2
[[ $rev =~ ^[a-f0-9]{64}$ ]]
mkdir -p "$rev"
cd "$rev"
case "$phase" in
    zavislosti)
        cp /opt/polarita-web-src/package*.json .
        npm ci --ignore-scripts --no-audit --no-fund --prefer-offline --maxsockets=3 --registry=https://registry.npmjs.org
        ;;
    sestaveni)
        test -f .zavislosti.ok
        rm -rf src public dist .astro
        cp -r /opt/polarita-web-src/{src,public} .
        cp /opt/polarita-web-src/{astro.config.mjs,tsconfig.json} .
        npm run build
        ;;
    *) exit 2 ;;
esac
printf '%s\n' "$rev" > ".$phase.next"
mv -T ".$phase.next" ".$phase.ok"
