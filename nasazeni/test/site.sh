#!/bin/sh
# Spouští se jako root uvnitř firemní VM po inicializaci jejího Incusu.
set -eu
test "$(hostname -s)" = polarita-hq
test "$(systemd-detect-virt)" = kvm
src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd /srv/polarita/infra/incus
test -f .terraform.lock.hcl
test "$(incus storage get default source)" = polarita_zfs/data/incus/pool
install -d /etc/polarita
nft -c -f "$src/zones.nft"
install -m 644 "$src/zones.nft" /etc/polarita/zones.nft
install -m 644 "$src/polarita-zones.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable polarita-zones.service
systemctl start polarita-zones.service
nft -f /etc/polarita/zones.nft
if [ "$#" -gt 0 ]; then
    python3 - "$1" <<'DNS'
import json, re, sys
from pathlib import Path
if not re.fullmatch(r"[a-z0-9.-]+[.]ts[.]net",sys.argv[1]):
    raise SystemExit("Neplatné jméno vydavatele identity")
p = Path("oidc.auto.tfvars.json")
tmp = p.with_suffix(".next")
tmp.write_text(json.dumps({"oidc_fqdn":sys.argv[1]}) + "\n")
tmp.replace(p)
DNS
fi
install -m 644 "$src/zones.tf" zones.tf
tofu fmt -check
tofu init -input=false -lockfile=readonly
tofu validate
plan=$(mktemp)
trap 'rm -f "$plan"' EXIT
tofu plan -input=false -out="$plan"
# Sdílený pracovní adresář může obsahovat i jiné služby. Nesmí dojít k jejich změně.
tofu show -json "$plan" | python3 -c '
import json, sys
for resource in json.load(sys.stdin).get("resource_changes", []):
    actions = resource["change"]["actions"]
    if actions in (["no-op"], ["read"]):
        continue
    if resource["address"].startswith(("incus_network.zone[", "incus_profile.zone[")) and actions == ["create"]:
        continue
    if resource["address"] in ("incus_network.zone[\"dmz_edge\"]", "incus_network.zone[\"app_internal\"]") and actions == ["update"]:
        before = dict(resource["change"]["before"]["config"])
        after = dict(resource["change"]["after"]["config"])
        before.pop("raw.dnsmasq", None)
        after.pop("raw.dnsmasq", None)
        if before == after:
            continue
    sys.exit("Neočekávaná změna: " + resource["address"])
'
tofu apply -input=false "$plan"
tofu plan -input=false -detailed-exitcode
