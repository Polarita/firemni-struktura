#!/bin/bash
# Serverové vydání a obraz pro linux/amd64 od téhož vydavatele.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
work=/srv/polarita/infra/zulip-test/zdroje
install -d -m 0750 "$work"
cd "$work"
exec 9>.priprava
flock 9
archive=zulip-server-13.3.tar.gz
digest=9fb82bab771ec4690590014b8416197ba3d25fa74a09fd57d555ef0713229d36
if [[ ! -f $archive ]] || ! printf '%s  %s\n' "$digest" "$archive" | sha256sum -c --status; then
    tmp=$(mktemp -p "$work" .stazeni-XXXXXXXX)
    trap 'rm -f -- "$tmp"' EXIT
    curl --proto '=https' --fail --silent --show-error --location --retry 3 \
        "https://download.zulip.com/server/$archive" -o "$tmp"
    printf '%s  %s\n' "$digest" "$tmp" | sha256sum -c
    mv -T "$tmp" "$archive"
fi
id=zulip/zulip-server@sha256:58e376cc7f599dc3ab466c02015616cf10e7b5e4756b8774d2d28916a70d6ad4
alias=polarita-zulip-13.3-0
if ! incus image info "$alias" >/dev/null 2>&1; then
    incus image copy "ghcr:$id" local: --alias "$alias"
fi
[[ $(incus image get-property "$alias" id) == "$id" ]]
[[ $(incus image get-property "$alias" oci.source) == https://github.com/zulip/docker-zulip ]]
echo 'Zulip 13.3 má ověřený archiv a místní obraz pro x86-64 připravený k instalaci.'
