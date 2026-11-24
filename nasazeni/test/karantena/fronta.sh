#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/karantena-test
vm=karantena-test
exec 9>"$work/.instalace"
flock 9
[[ $(incus list "$vm" -c s -f csv) == STOPPED ]]
incus start "$vm"
trap 'incus stop "$vm" --timeout 180 </dev/null' EXIT
for i in {1..120}; do
    if incus exec -T "$vm" -- mountpoint -q /mnt/clamav-db 2>/dev/null; then break; fi
    sleep 1
done
bash "$src/podman.sh"
incus file push --mode=0700 "$src/pracovni-vm.sh" "$vm/run/polarita-priprav-pracovnika"
incus exec -T "$vm" -- bash /run/polarita-priprav-pracovnika </dev/null
incus file push --mode=0644 "$src/pracovnik.py" "$vm/opt/polarita/karantena.py"
incus stop "$vm" --timeout 180
trap - EXIT
install -d -m 0750 "$work/bin"
install -m 0644 "$src/prijem.py" "$src/zpracovani.py" "$work/bin/"
install -d -m 0700 /srv/polarita/workspace/karantena/vstup
install -m 0644 "$src"/polarita-karantena.{service,path,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-karantena.path polarita-karantena.timer
