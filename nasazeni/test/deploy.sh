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
trap 'rm -rf "$tmp"' EXIT
CGO_ENABLED=0 go build -trimpath -o "$tmp/portal" nasazeni/test/portal.go
"${inc[@]}" file push --mode 0755 --project polarita "$tmp/portal" "polarita-hq$dest/portal"
"${guest[@]}" "$dest/nasazeni/test/site.sh"
"${guest[@]}" "$dest/nasazeni/test/portal.sh" "$dest/portal"
sudo -n bash nasazeni/test/vstup.sh
fqdn=$(tailscale status --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
"${guest[@]}" cat /srv/polarita/vault/test-login/heslo | python3 nasazeni/test/smoke.py "https://$fqdn"
"${guest[@]}" sh -ec 'ln -sfn "$1" /srv/polarita/infra/releases/.current-new; mv -Tf /srv/polarita/infra/releases/.current-new /srv/polarita/infra/releases/current' deploy "$dest"
