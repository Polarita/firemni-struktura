#!/bin/bash
# Spouští správce na Ejpovicích. Produkční data a důkazy mají samostatné umístění.
set -euo pipefail
[[ $(hostname -s) == ejpovice ]]
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
tag=$(python3 -c 'import json; print(json.load(open("nastroje/kanon.json"))["release_tag"])')
commit=$(git rev-parse HEAD)
[[ $(git rev-list -n 1 "$tag") == "$commit" ]]
git diff --quiet HEAD -- nasazeni/test
inc=(sudo -n incus)
guest=("${inc[@]}" exec -T --project polarita polarita-hq --)
[[ $("${guest[@]}" hostname -s) == polarita-hq ]]
dest=/srv/polarita/infra/releases/$commit
"${guest[@]}" install -d "$dest"
git archive "$commit" | "${guest[@]}" tar -x -C "$dest"
tmp=$(mktemp -d)
vpn_tmp=$("${guest[@]}" mktemp -d /run/polarita-vpn-test-XXXXXXXX)
trap 'rm -rf "$tmp"; "${guest[@]}" rm -rf -- "$vpn_tmp"' EXIT
CGO_ENABLED=0 go build -trimpath -o "$tmp/portal" nasazeni/test/portal.go
"${inc[@]}" file push --mode 0755 --project polarita "$tmp/portal" "polarita-hq$dest/portal"
"${guest[@]}" "$dest/nasazeni/test/incus.sh"
"${guest[@]}" "$dest/nasazeni/test/site.sh"
"${guest[@]}" "$dest/nasazeni/test/portal.sh" "$dest/portal"
"${guest[@]}" "$dest/nasazeni/test/hrana.sh"
"${guest[@]}" curl -fsS --retry 4 --retry-connrefused -o /dev/null http://127.0.0.1:18184/
sudo -n bash nasazeni/test/vstup.sh
fqdn=$(tailscale status --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
"${guest[@]}" cat /srv/polarita/vault/test-login/heslo | python3 nasazeni/test/smoke.py "https://$fqdn"
"${inc[@]}" file push --project polarita "$(command -v tailscale)" "$(command -v tailscaled || echo /usr/sbin/tailscaled)" "polarita-hq$vpn_tmp/"
"${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-03
"${guest[@]}" "$dest/nasazeni/test/mx.sh" | tee "$tmp/mx.txt"
"${inc[@]}" file push --project polarita "$tmp/mx.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-03/mx-$commit.txt"
"${guest[@]}" "$dest/nasazeni/test/ochrana.sh"
"${guest[@]}" python3 "$dest/nasazeni/test/ochrana/zkouska.py" | tee "$tmp/ochrana.txt"
"${inc[@]}" file push --project polarita "$tmp/ochrana.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-03/ochrana-$commit.txt"
if command -v dig >/dev/null; then
    bash nasazeni/test/hrana/inventura-dns.sh >"$tmp/dns.txt"
    "${inc[@]}" file push --project polarita "$tmp/dns.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-03/verejne-dns-$commit.txt"
fi
"${guest[@]}" python3 "$dest/nasazeni/test/hrana/zkouska-vpn.py" "$vpn_tmp" | tee "$tmp/zkouska-vpn.txt"
"${inc[@]}" file push --project polarita "$tmp/zkouska-vpn.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-03/zkouska-vpn-$commit.txt"
CGO_ENABLED=0 go build -trimpath -o "$tmp/agent" nasazeni/test/trezor/agent.go
"${inc[@]}" file push --mode 0755 --project polarita "$tmp/agent" "polarita-hq$dest/agent"
"${guest[@]}" bash "$dest/nasazeni/test/hesla/instalace.sh" "https://$fqdn/hesla" | tee "$tmp/hesla.txt"
"${guest[@]}" python3 "$dest/nasazeni/test/hesla/obnova.py" | tee "$tmp/obnova-hesel.txt"
sudo -n bash nasazeni/test/trezor/prijemce.sh
if "${guest[@]}" test -e /srv/polarita/vault/openbao-test/inicializovano; then
    sudo -n python3 nasazeni/test/trezor/rozsireni.py "$dest/nasazeni/test/trezor"
fi
"${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-04
"${guest[@]}" bash "$dest/nasazeni/test/trezor/instalace.sh" "$dest/agent" | tee "$tmp/trezor.txt"
"${guest[@]}" bash "$dest/nasazeni/test/trezor/zkouska-startu.sh" | tee "$tmp/restart.txt"
sudo -n python3 nasazeni/test/trezor/zkouska-obnovy.py "$dest/nasazeni/test/trezor" | tee "$tmp/obnova.txt"
for proof in trezor restart obnova hesla obnova-hesel; do
    "${inc[@]}" file push --project polarita "$tmp/$proof.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-04/$proof-$commit.txt"
done
# Starší vydání vytvořilo přímý vstup. Odstraň ho až po ověření nové cesty.
if [[ $("${guest[@]}" incus config device get reditelstvi-test portal listen 2>/dev/null || true) == tcp:127.0.0.1:18182 ]]; then
    "${guest[@]}" incus config device remove reditelstvi-test portal
fi
"${guest[@]}" sh -ec 'ln -sfn "$1" /srv/polarita/infra/releases/.current-new; mv -Tf /srv/polarita/infra/releases/.current-new /srv/polarita/infra/releases/current' deploy "$dest"
printf 'Ověřené přihlášení ve VPN: https://%s/\n' "$fqdn"
