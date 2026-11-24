#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/hrana
install -d -m 0755 "$work/conf" "$work/headscale"
cd "$work"
install -m 0644 "$src/hrana/hrana.tf" "$src/incus/providers.tf" "$src/incus/.terraform.lock.hcl" .
# Adresář je do instance připojen jen pro čtení. Výměna souboru je atomická.
install -m 0644 "$src/hrana/Caddyfile" conf/.Caddyfile.next
if incus info caddy-test >/dev/null 2>&1; then
    incus exec caddy-test -- caddy validate --adapter caddyfile --config /etc/caddy/.Caddyfile.next
fi
mv -f conf/.Caddyfile.next conf/Caddyfile
for pair in headscale.yaml:config.yaml policy.hujson:policy.hujson derp.yaml:derp.yaml; do
    source_file="$src/hrana/${pair%:*}"
    target="headscale/${pair#*:}"
    if ! cmp -s "$source_file" "$target"; then
        install -m 0644 "$source_file" "$target.next"
        mv -f "$target.next" "$target"
    fi
done
tofu fmt -check
tofu init -input=false -lockfile=readonly
tofu validate
plan=$(mktemp)
trap 'rm -f "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("resource_changes", []):
    if r["change"]["actions"] in (["read"], ["no-op"]): continue
    if r["address"] in {"incus_instance.caddy", "incus_instance.headscale", "incus_storage_volume.headscale"} and r["change"]["actions"] in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna: " + r["address"])
'
tofu apply -input=false "$plan"
sum=$(sha256sum headscale/* | sha256sum | cut -d' ' -f1)
if [[ ! -f .headscale-applied || $(cat .headscale-applied) != "$sum" ]]; then
    incus restart headscale-test
fi
incus exec headscale-test -- /ko-app/headscale configtest
incus exec caddy-test -- caddy validate --config /etc/caddy/Caddyfile
incus exec caddy-test -- caddy reload --config /etc/caddy/Caddyfile
tofu plan -input=false -detailed-exitcode
incus exec caddy-test -- cat /data/caddy/pki/authorities/local/root.crt >"$work/headscale-test-ca.crt"
curl --noproxy '*' -fsS --retry 4 --retry-all-errors --retry-delay 1 \
    --resolve vpn.polarita.test:8443:10.239.31.10 --cacert "$work/headscale-test-ca.crt" \
    https://vpn.polarita.test:8443/health | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"] == "pass"'
printf '%s\n' "$sum" > .headscale-applied
install -m 0755 "$src/hrana/zaloha.sh" "$work/"
install -m 0644 "$src"/hrana/polarita-headscale-zaloha.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-headscale-zaloha.timer
systemctl start polarita-headscale-zaloha.service
