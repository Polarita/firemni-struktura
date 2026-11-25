#!/bin/bash
# APT ověřuje balíky v polarita-hq, cílový kontejner instalaci dokončí bez sítě.
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
target=$1
shift
[[ $target == asterisk-test || $target == zulip-fronta-test || $target == checkmk-test || $target == postgres-test || $target == gitea-test || $target == gitea-runner-test || $target == aigis-build-test || $target == qet-nastroje-test || $target == restic-test || $target =~ ^restic-obnova-[a-f0-9]{12}$ ]]
[[ $# -gt 0 ]]
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
incus file pull "$target/var/lib/dpkg/status" "$tmp/status"
if python3 - "$tmp/status" "$@" <<'PY'
from email.parser import Parser
from pathlib import Path
import sys
installed = {}
for record in Path(sys.argv[1]).read_text().split("\n\n"):
    fields = Parser().parsestr(record, headersonly=True)
    if fields.get("Status") == "install ok installed":
        installed[fields["Package"]] = fields["Version"]
sys.exit(int(any(installed.get(name) != version for name, version in (arg.split("=", 1) for arg in sys.argv[2:]))))
PY
then exit 0; fi
install -d -m 0755 "$tmp/deb/partial"
apt-get -o "Dir::State::status=$tmp/status" -o "Dir::Cache::archives=$tmp/deb" --download-only --no-install-recommends -y install "$@"
inside=(incus exec -T "$target" --)
stage_root=/run
if [[ $target == asterisk-test || $target == aigis-build-test || $target == gitea-runner-test || $target == qet-nastroje-test ]]; then stage_root=/var/tmp; fi
stage=$("${inside[@]}" mktemp -d "$stage_root/polarita-deb-XXXXXXXX")
[[ $stage == "$stage_root"/polarita-deb-* ]]
"${inside[@]}" install -d -m 0755 "$stage/lists/partial"
tar -cf - -C "$tmp/deb" . | "${inside[@]}" tar -xf - -C "$stage"
incus file push --mode=0755 "$src/instaluj-deb.sh" "$target$stage/instaluj-deb.sh"
# Šablona editoru používá pouze Xvfb. Nad celou instalací dohlíží služba
# v polarita-hq, i když uvnitř šablony není dostupná systémová sběrnice.
if [[ $stage_root == /run || $target == qet-nastroje-test ]]; then
    "${inside[@]}" sh "$stage/instaluj-deb.sh" "$stage"
    exit 0
fi
# Delší instalace musí pokračovat i po odpojení klienta Incus.
unit=polarita-balicky-${stage##*/}
if ! "${inside[@]}" systemd-run --quiet --unit="$unit" --property=Type=exec --property=RemainAfterExit=yes \
        /bin/sh "$stage/instaluj-deb.sh" "$stage"; then
    # Odpověď se mohla ztratit až po registraci služby.
    "${inside[@]}" systemctl cat "$unit.service" >/dev/null
fi
for ((i=0; i<480; i++)); do
    if state=$("${inside[@]}" systemctl show "$unit.service" --value -p SubState); then
        case $state in
            exited)
                "${inside[@]}" systemctl stop "$unit.service"
                exit 0 ;;
            failed|dead)
                "${inside[@]}" journalctl -u "$unit.service" -n 30 --no-pager
                exit 1 ;;
        esac
    fi
    sleep 15
done
printf 'Instalace balíků %s v %s stále čeká na výsledek.\n' "$unit" "$target" >&2
exit 1
