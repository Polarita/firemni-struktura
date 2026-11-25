#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
if (( EUID != 0 )); then exec sudo -n -- /usr/local/sbin/agent_vault "$@"; fi
actor=instalace
if [[ ${SUDO_USER:-} =~ ^pol-vault-(1[1-8][0-9]{3})$ ]]; then actor=${BASH_REMATCH[1]}; fi
root=/opt/polarita-agent-vault
dir=$(readlink -e "$root/current")
[[ $dir =~ ^/opt/polarita-agent-vault/[0-9a-f]{64}$ ]]
common=(-p User=polarita-pamet -p UMask=0077 -p PrivateNetwork=yes -p RestrictAddressFamilies=AF_UNIX
    -p ProtectSystem=strict -p ProtectHome=yes -p PrivateTmp=yes -p NoNewPrivileges=yes -p PrivateDevices=yes
    -p CapabilityBoundingSet= -p InaccessiblePaths=/srv/polarita/data -p InaccessiblePaths=/srv/polarita/workspace
    -E "POLARITA_VAULT_ACTOR=$actor" -E OPENBLAS_NUM_THREADS=1 -E TOKENIZERS_PARALLELISM=false)
run=(systemd-run --quiet --pipe --wait --collect --service-type=exec)
python=("$dir/sdk/bin/python" -Es "$dir/cli.py")
case ${1:-} in
    get-context) exec "${run[@]}" "${common[@]}" "${python[@]}" "$@" ;;
    prijmi-doklady)
        [[ $# == 1 && $actor == instalace ]]
        exec "${run[@]}" "${common[@]}" -p ReadWritePaths=/srv/polarita/vault "${python[@]}" "$@"
        ;;
    log|adr) exec "${run[@]}" "${common[@]}" -p ReadWritePaths=/srv/polarita/vault "${python[@]}" "$@" ;;
    search|index)
        # Jediná aktivní inference sdílí dostupnou paměť VM mezi dvaceti rolemi.
        exec 8>/run/polarita-agent-vault-model.lock
        flock 8
        # Připoj jen běžící unixový socket PostgreSQL. Pracovní proces nemá přístup do Incusu ani do jeho sítě.
        pid=$(incus query /1.0/instances/postgres-test/state | python3 -c 'import json,sys; print(int(json.load(sys.stdin)["pid"]))')
        [[ $pid =~ ^[1-9][0-9]*$ && -S /proc/$pid/root/run/postgresql/.s.PGSQL.5432 ]]
        install -dm0700 /run/polarita-agent-vault-cil
        ln -sfn "/proc/$pid/root/run/postgresql/.s.PGSQL.5432" /run/polarita-agent-vault-cil/.socket-next
        mv -Tf /run/polarita-agent-vault-cil/.socket-next /run/polarita-agent-vault-cil/socket
        cred=/srv/polarita/data/bootstrap-test/agent-vault
        if [[ $1 == index ]]; then
            exec "${run[@]}" "${common[@]}" -p "LoadCredential=postgres:$cred/index" "${python[@]}" "$@"
        fi
        "${run[@]}" "${common[@]}" -p "LoadCredential=postgres:$cred/index" "${python[@]}" index </dev/null >/dev/null
        exec "${run[@]}" "${common[@]}" -p "LoadCredential=postgres:$cred/read" "${python[@]}" "$@"
        ;;
    *) echo 'Použití: agent_vault get-context [cesta] | search dotaz [--limit n] | log identifikátor | adr identifikátor' >&2; exit 2 ;;
esac
