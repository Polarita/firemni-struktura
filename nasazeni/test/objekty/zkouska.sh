#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/garage-test
exec 9>"$work/.instalace"
flock 9
python3 "$src/provoz.py"
ln -sfn "$(dirname "$src")" "$work/.zdroje-nove"
mv -Tf "$work/.zdroje-nove" "$work/zdroje"
install -m 0644 "$src"/polarita-garage-expirace.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-garage-expirace.timer
systemctl start polarita-garage-expirace.service
systemctl is-active --quiet polarita-garage-expirace.timer
