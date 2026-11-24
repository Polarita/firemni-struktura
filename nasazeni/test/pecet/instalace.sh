#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/pecet-test
install -d -m 0750 "$work/tofu"
exec 9>"$work/.instalace"
flock 9
python3 "$src/balicky.py" "$work/wheels"
chmod 0755 "$work/wheels"
image=$(sed -nE 's/^ *image *= *"local:([[:xdigit:]]{64})"$/\1/p' "$src/pecet.tf")
[[ $image =~ ^[0-9a-f]{64}$ ]]
if ! incus image info "$image" >/dev/null 2>&1; then
    incus image copy "images:$image" local:
fi
cd "$work/tofu"
install -m 0644 "$src/pecet.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
tofu init -input=false -lockfile=readonly
tofu validate
plan=$(mktemp)
trap 'rm -f "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes", []):
    a = r["change"]["actions"]
    if a in (["no-op"], ["read"]): continue
    if r["address"] == "incus_instance.pecet" and a in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna " + r["address"])'
tofu apply -input=false "$plan"
incus exec -T pecet-test -- bash -ec '
for i in {1..60}; do if mountpoint -q /run && test -S /run/systemd/private; then break; fi; sleep 1; done
command -v python3
python3 -m venv --without-pip /opt/polarita-pecet
export PYTHONPATH=/opt/pecet-wheels/pip-26.3-py3-none-any.whl
/opt/polarita-pecet/bin/python -m pip --disable-pip-version-check install --no-index --find-links /opt/pecet-wheels pyhanko==0.38.2
/opt/polarita-pecet/bin/python -m pip check'
incus file push --mode=0644 "$src/dokument.py" pecet-test/opt/polarita-pecet/dokument.py
tofu plan -input=false -detailed-exitcode
