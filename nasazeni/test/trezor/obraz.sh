#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
work=/srv/polarita/infra/openbao-test
install -d -m 0750 "$work/balicky"
cd "$work/balicky"
pkg=openbao_2.7.3_linux_amd64.deb
sha=0800c71469c1d7a5d5c9fb37ce0e441cad97d9fe122dab70391c8371e290b935
base=0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50
alias=polarita-openbao-test-2.7.3
url=https://github.com/openbao/openbao/releases/download/v2.7.3
tmp=$(mktemp -d /run/bao-obraz-XXXXXXXX)
builder=bao-build-${tmp##*-}
trap 'if [[ -e "$tmp/builder" ]]; then incus delete -f "$builder"; fi; rm -rf "$tmp"' EXIT
if ! echo "$sha  $pkg" | sha256sum --check --status 2>/dev/null; then
    curl -fsSL --retry 3 "$url/$pkg" -o "$pkg.next"
    echo "$sha  $pkg.next" | sha256sum -c -
    mv -f "$pkg.next" "$pkg"
fi
if [[ ! -s overovaci.asc ]]; then
    curl -fsSL --retry 3 https://openbao.org/assets/openbao-gpg-pub-20240618.asc -o overovaci.asc.next
    mv overovaci.asc.next overovaci.asc
fi
if [[ ! -s $pkg.gpgsig ]]; then
    curl -fsSL --retry 3 "$url/$pkg.gpgsig" -o "$pkg.gpgsig.next"
    mv "$pkg.gpgsig.next" "$pkg.gpgsig"
fi
gpg --homedir "$tmp" --batch --dearmor --output "$tmp/overovaci.gpg" overovaci.asc
gpgv --homedir "$tmp" --keyring "$tmp/overovaci.gpg" --status-fd=1 "$pkg.gpgsig" "$pkg" >"$tmp/podpis"
grep -E '^\[GNUPG:\] VALIDSIG .* 66D15FDD87287219C8E15478D200CD702853E6D0$' "$tmp/podpis"
if ! incus image info "$alias" >/dev/null 2>&1; then
    if ! incus image info "$base" >/dev/null 2>&1; then base=images:ubuntu/26.04; fi
    incus init "$base" "$builder" -p default -p sandbox_airgap </dev/null
    touch "$tmp/builder"
    dpkg-deb --fsys-tarfile "$pkg" | tar -xO ./usr/bin/bao | incus file push --mode=0755 - "$builder/usr/local/bin/bao"
    incus publish "$builder" --alias "$alias" description="Polarita OpenBao 2.7.3 TEST" </dev/null
fi
dpkg-deb --fsys-tarfile "$pkg" | tar -xO ./usr/bin/bao | sha256sum | cut -d' ' -f1 > "$work/bao.sha256"
