#!/bin/bash
# APT ověřuje balíky v polarita-hq, cílový kontejner instalaci dokončí bez sítě.
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
target=$1
shift
[[ $target == zulip-fronta-test || $target == checkmk-test || $target == postgres-test || $target == gitea-test || $target == gitea-runner-test || $target == aigis-build-test || $target == restic-test || $target =~ ^restic-obnova-[a-f0-9]{12}$ ]]
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
if [[ $target == aigis-build-test ]]; then stage_root=/var/tmp; fi
stage=$("${inside[@]}" mktemp -d "$stage_root/polarita-deb-XXXXXXXX")
[[ $stage == "$stage_root"/polarita-deb-* ]]
"${inside[@]}" install -d -m 0755 "$stage/lists/partial"
tar -cf - -C "$tmp/deb" . | "${inside[@]}" tar -xf - -C "$stage"
"${inside[@]}" sh -ec 'd=$1; trap '\''rm -r -- "$d"'\'' EXIT; DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends -o "Dir::State::Lists=$d/lists" -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=- install "$d"/*.deb' install "$stage"
