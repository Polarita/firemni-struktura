#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
[[ $src =~ ^/srv/polarita/infra/(releases|stavba)/[0-9a-f]{40}/nasazeni/test/git$ ]]
tmp=$(mktemp)
trap 'rm -- "$tmp"' EXIT
cat >"$tmp" <<UNIT
[Unit]
Description=Přidělení čekající úlohy jednorázovému pracovníku CI
After=polarita-gitea-runner.service
Requires=polarita-gitea-runner.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $src/registrace.py --cekajici
TimeoutStartSec=90s
UNIT
install -m 0644 "$tmp" /etc/systemd/system/polarita-ci-fronta.service
install -m 0644 "$src/polarita-ci-fronta.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-ci-fronta.timer
systemctl start polarita-ci-fronta.service
