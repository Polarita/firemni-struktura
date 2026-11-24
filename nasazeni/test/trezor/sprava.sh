#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $(id -u) == 0 ]]
work=/srv/polarita/infra/openbao-test
case "${1:-}" in
    uzamknout)
        exec 9>"$work/.start-lock"
        flock 9
        touch "$work/uzamceno"
        incus exec openbao-test -- systemctl stop openbao
        incus exec openbao-test -- test ! -e /run/openbao-seal/klíč
        ;;
    odemknout)
        rm -f "$work/uzamceno"
        systemctl start polarita-openbao-start.service
        curl --retry 20 --retry-delay 1 --retry-all-errors --max-time 3 --fail --silent --noproxy '*' --cacert "$work/ca.crt" https://10.239.33.10:8200/v1/sys/health >/dev/null
        ;;
    *) echo 'Použití: sprava.sh uzamknout|odemknout' >&2; exit 2 ;;
esac
