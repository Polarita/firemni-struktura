#!/bin/bash
# Stejná verze RocksDB jako v Cargo.lock Stalwartu 1.2.0, také pro obnovené tabulky formátu 7.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
dir=/opt/polarita-rocksdb
digest=826c39c35f6a59b7ec9833dd0a813188f310506129ef5e19518611ddbc67ad2d
signer=3D1953B24F393EE26CD3704E8AFAC6063ADCAF77
url=https://repo.maven.apache.org/maven2/org/rocksdb/rocksdbjni/11.8.1/rocksdbjni-11.8.1-linux64.jar
install -d -m 0755 "$dir"
exec 8>"$dir/.install"
flock 8
if [[ ! -f $dir/rocksdbjni.jar ]] || ! printf '%s  %s\n' "$digest" "$dir/rocksdbjni.jar" | sha256sum --status -c; then
    tmp=$(mktemp -d "$dir/.stazeni-XXXXXXXX")
    trap 'rm -r -- "$tmp"' EXIT
    curl -fsSL --retry 3 "$url" -o "$tmp/lib.jar"
    curl -fsSL --retry 3 "$url.asc" -o "$tmp/lib.asc"
    curl -fsSL --retry 3 "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x$signer" -o "$tmp/pub.asc"
    printf '%s  %s\n' "$digest" "$tmp/lib.jar" | sha256sum -c
    gpg --batch --dearmor -o "$tmp/keys.gpg" "$tmp/pub.asc"
    gpgv --homedir "$tmp" --status-fd 1 --keyring "$tmp/keys.gpg" "$tmp/lib.asc" "$tmp/lib.jar" |
        awk -v signer="$signer" '$2=="VALIDSIG" && ($3==signer || $NF==signer) {ok=1} END {exit !ok}'
    chmod 0644 "$tmp/lib.jar"
    mv -T "$tmp/lib.jar" "$dir/rocksdbjni.jar"
fi
DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 -y --no-install-recommends install openjdk-21-jdk-headless=21.0.13.1+2-1~26.04.1
classes=$(mktemp -d "$dir/.javac-XXXXXXXX")
trap 'rm -r -- "${classes:?}"; if [[ -n ${tmp:-} ]]; then rm -r -- "$tmp"; fi' EXIT
javac --release 21 -cp "$dir/rocksdbjni.jar" -d "$classes" "$src/RocksSonda.java"
install -m 0644 "$classes/RocksSonda.class" "$dir/.RocksSonda.class.next"
mv -T "$dir/.RocksSonda.class.next" "$dir/RocksSonda.class"
