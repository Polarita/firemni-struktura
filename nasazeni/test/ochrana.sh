#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
src=$(cd "$(dirname "$0")/ochrana" && pwd)
work=/srv/polarita/infra/crowdsec-test
install -d -m 0750 "$work"
cd "$work"
exec 9>".install.lock"
flock 9
install -d -m 0750 bin balicky data conf conf/hub conf/parsers/s00-raw conf/scenarios
version=1.8.2
base=crowdsec-v$version
archive=balicky/crowdsec-release.tgz
sha=6e0b2add0ff3231dca3db7146834d7fea028215b915e2da39ebe30fc9f11436f
if ! echo "$sha  $archive" | sha256sum --check --status 2>/dev/null; then
    curl -fsSL --retry 3 "https://github.com/crowdsecurity/crowdsec/releases/download/v$version/crowdsec-release.tgz" -o "$archive.next"
    echo "$sha  $archive.next" | sha256sum -c -
    mv -f "$archive.next" "$archive"
fi
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
tar -xf "$archive" -C "$tmp" "$base/config/patterns" "$base/config/simulation.yaml" \
    "$base/cmd/crowdsec/crowdsec" "$base/cmd/crowdsec-cli/cscli"
for file in "$base/cmd/crowdsec/crowdsec" "$base/cmd/crowdsec-cli/cscli"; do
    if ! cmp -s "$tmp/$file" "bin/${file##*/}"; then
        install -m 0755 "$tmp/$file" "bin/${file##*/}.next"
        mv -f "bin/${file##*/}.next" "bin/${file##*/}"
    fi
done
cp -r "$tmp/$base/config/patterns" conf/
install -m 0644 "$tmp/$base/config/simulation.yaml" "$src"/{config,profiles,acquis}.yaml conf/
install -m 0644 "$src"/{caddy,stalwart}.yaml conf/parsers/s00-raw/
install -m 0644 "$src/scenario.yaml" conf/scenarios/
index=conf/hub/.index.json
index_sum=cef4535c98d0e1180ae8deb7df70f2bb42a136d3a2e74f8c7380215a5e42a85b
if ! echo "$index_sum  $index" | sha256sum --check --status 2>/dev/null; then
    curl -fsSL --retry 3 https://raw.githubusercontent.com/crowdsecurity/hub/999fb5de42e29da968188f77253244b7864091dd/.index.json -o "$index.next"
    echo "$index_sum  $index.next" | sha256sum -c -
    mv -f "$index.next" "$index"
fi
cfg=$work/conf/config.yaml
creds=$work/conf/local_api_credentials.yaml
if [[ ! -s $creds ]]; then
    (umask 077; bin/cscli -c "$cfg" machines add --auto --url http://127.0.0.1:18280 -f "$creds")
fi
chmod 0600 "$creds"
bin/crowdsec -c "$cfg" -no-capi -t
install -m 0644 "$src/polarita-crowdsec.service" /etc/systemd/system/
systemctl daemon-reload
digest=$(sha256sum "$src"/* | sha256sum)
if [[ ! -f .applied || $(cat .applied) != "$digest" ]]; then systemctl restart polarita-crowdsec.service; fi
systemctl enable --now polarita-crowdsec.service
bin/cscli -c "$cfg" lapi status
printf '%s\n' "$digest" >.applied
bouncer_version=0.0.38
bouncer_sha=3cb7ca302438ede690849218d585dee6cbba7915982f79f3dd45024a9eced31e
archive=balicky/bouncer.tgz
if ! echo "$bouncer_sha  $archive" | sha256sum --check --status 2>/dev/null; then
    curl -fsSL --retry 3 "https://github.com/crowdsecurity/cs-firewall-bouncer/releases/download/v$bouncer_version/crowdsec-firewall-bouncer-linux-amd64.tgz" -o "$archive.next"
    echo "$bouncer_sha  $archive.next" | sha256sum -c -
    mv -f "$archive.next" "$archive"
fi
exe=crowdsec-firewall-bouncer
tar -xf "$archive" -C "$tmp" "$exe-v$bouncer_version/$exe"
if ! cmp -s "$tmp/$exe-v$bouncer_version/$exe" "bin/$exe"; then
    install -m 0755 "$tmp/$exe-v$bouncer_version/$exe" "bin/$exe.next"
    mv -f "bin/$exe.next" "bin/$exe"
fi
install -m 0755 "$src/firewall.sh" bin/
key=conf/bouncer.key
if [[ ! -s $key && -s $key.next ]] && grep -Eq '^[[:alnum:]_+=/-]{20,}$' "$key.next"; then
    mv -f "$key.next" "$key"
fi
if [[ ! -s $key ]]; then
    (umask 077; bin/cscli -c "$cfg" bouncers add polarita-mx-dmz -o raw > "$key.next")
    grep -Eq '^[[:alnum:]_+=/-]{20,}$' "$key.next"
    mv -f "$key.next" "$key"
fi
python3 - "$src/bouncer.yaml" <<'PY'
import os, pathlib, sys
os.umask(0o077)
tmp = pathlib.Path("conf/bouncer-local.yaml.next")
tmp.write_text(pathlib.Path(sys.argv[1]).read_text().replace("__LOCAL_KEY__", pathlib.Path("conf/bouncer.key").read_text().strip()))
tmp.replace("conf/bouncer-local.yaml")
PY
install -m 0644 "$src/polarita-crowdsec-bouncer.service" /etc/systemd/system/
systemctl daemon-reload
if [[ ! -f .bouncer-applied || $(cat .bouncer-applied) != "$digest" ]]; then
    systemctl restart polarita-crowdsec-bouncer.service
fi
systemctl enable --now polarita-crowdsec-bouncer.service
printf '%s\n' "$digest" >.bouncer-applied
