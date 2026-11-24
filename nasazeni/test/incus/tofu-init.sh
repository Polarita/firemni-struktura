#!/bin/bash
# Jedna ověřená kopie poskytovatele pro moduly téže verze uvnitř polarita-hq.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
cmp .terraform.lock.hcl "$src/.terraform.lock.hcl"
cache=/srv/polarita/infra/tofu-providers
install -d -m0755 "$cache"
read -r digest _ < <(sha256sum .terraform.lock.hcl)
mirror="$cache/$digest-$(uname -m)"
exec 9>"$cache/.priprava"
flock 9
if [[ ! -d $mirror ]]; then
    tmp=$(mktemp -d "$cache/.priprava-XXXXXXXX")
    trap 'rm -rf -- "$tmp"' EXIT
    install -m0644 "$src/providers.tf" "$src/.terraform.lock.hcl" "$tmp/"
    init=(tofu -chdir="$tmp" init -input=false -backend=false -lockfile=readonly)
    ready=false
    for previous in /srv/polarita/infra/incus /srv/polarita/infra/hrana; do
        if [[ -d $previous/.terraform/providers ]] && cmp -s .terraform.lock.hcl "$previous/.terraform.lock.hcl"; then
            if "${init[@]}" -plugin-dir="$previous/.terraform/providers"; then
                ready=true
                break
            fi
        fi
    done
    if [[ $ready != true ]]; then "${init[@]}"; fi
    # OpenTofu může do .terraform vložit symlink na starší modul. Zrcadlo má vlastní obsah.
    cp -RL -- "$tmp/.terraform/providers" "$tmp/overene"
    mv -T "$tmp/overene" "$mirror"
    rm -rf -- "$tmp"
    trap - EXIT
fi
flock -u 9
exec 9>&-
exec tofu init -input=false -lockfile=readonly -plugin-dir="$mirror"
