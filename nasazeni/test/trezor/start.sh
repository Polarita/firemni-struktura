#!/bin/bash
# Běží uvnitř firemní VM. Záměrně uzavřený trezor nechá uzavřený.
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
work=/srv/polarita/infra/openbao-test
dir=/srv/polarita/data/bootstrap-test/openbao-test
exec 9>"$work/.start-lock"
flock 9
[[ ! -e $work/uzamceno ]] || exit 0
vm=openbao-test
inside=(incus exec -T "$vm" --)
state=$(incus query "/1.0/instances/$vm/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')
if [[ $state == Stopped ]]; then incus start "$vm"; fi
# Po přerušení startu se na novém pokusu zahodí výhradně toto krátkodobé médium.
clean() {
    "${inside[@]}" sh -ec 'rm -f /run/openbao-seal/klíč; if mountpoint -q /run/openbao-seal; then umount /run/openbao-seal; fi'
}
if "${inside[@]}" systemctl is-active --quiet openbao.service; then
    if "${inside[@]}" mountpoint -q /run/openbao-seal; then clean; fi
    exit 0
fi
trap clean EXIT
clean
"${inside[@]}" sh -ec 'install -d -m 0700 /run/openbao-seal; mount -t tmpfs -o size=64k,mode=0750,nodev,noexec,nosuid tmpfs /run/openbao-seal; chgrp openbao /run/openbao-seal'
systemd-creds decrypt --name=bao-pecet "$dir/pecet.cred" - | "${inside[@]}" sh -ec 'umask 077; cat >/run/openbao-seal/klíč; chown openbao:openbao /run/openbao-seal/klíč; chmod 0400 /run/openbao-seal/klíč'
"${inside[@]}" systemctl start openbao.service
for i in {1..60}; do
    if health=$(curl --noproxy '*' -s --max-time 2 --cacert "$work/ca.crt" https://10.239.33.10:8200/v1/sys/health); then
        if python3 -c 'import json,sys; x=json.load(sys.stdin); sys.exit(int(x["initialized"] and x["sealed"]))' <<<"$health"; then
            exit 0
        fi
    fi
    sleep 1
done
echo 'OpenBao nedokončil načtení pečeti.' >&2
"${inside[@]}" systemctl stop openbao.service
exit 1
