#!/bin/bash
# Hotový obraz pro týdenní zkoušku obnovy nepotřebuje při výpadku přístup k balíčkovému zrcadlu.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
base=$(incus config get postgres-test volatile.base_image)
[[ $base =~ ^[a-f0-9]{64}$ ]]
bash "$src/rocks.sh"
rocks=/opt/polarita-rocksdb
packages=(git=1:2.53.0-1ubuntu1.1 pgbackrest=2.58.0-1 openjdk-21-jre-headless=21.0.13.1+2-1~26.04.1)
key=$(printf '%s\n' "$base" "${packages[@]}" "$(sha256sum "$rocks/RocksSonda.class" "$rocks/rocksdbjni.jar")" | sha256sum | cut -c1-20)
alias=polarita-restic-obnova-$key
work=/srv/polarita/infra/restic-test
exec 9>"$work/.obraz-obnovy"
flock 9
if ! incus image info "$alias" >/dev/null 2>&1; then
    builder=restic-obnova-$(openssl rand -hex 6)
    incus init "$base" "$builder" -p default -p sandbox_airgap -c limits.memory=384MiB
    trap 'incus delete --force "$builder" </dev/null' EXIT
    incus start "$builder"
    incus exec -T "$builder" -- bash -ec 'for i in {1..40}; do if test -S /run/systemd/private; then break; fi; sleep 1; done; [[ $(ls /sys/class/net) == lo ]]'
    bash "$src/../incus/balicky.sh" "$builder" "${packages[@]}"
    incus exec -T "$builder" -- bash -ec 'git --version; pgbackrest version; [[ ! -e /var/tmp/obnova-polarita && ! -e /var/lib/postgresql/obnova ]]'
    incus exec -T "$builder" -- install -d -m 0755 "$rocks"
    incus file push --mode=0644 "$rocks/"{RocksSonda.class,rocksdbjni.jar} "$builder$rocks/"
    incus stop "$builder"
    incus publish "$builder" --alias "$alias" description="Izolovaná obnova PostgreSQL, Git a pgBackRest TEST"
fi
fingerprint=$(incus image list "$alias" --format=json | python3 -c 'import sys,json; (x,)=json.load(sys.stdin); print(x["fingerprint"])')
[[ $fingerprint =~ ^[a-f0-9]{64}$ ]]
printf '%s %s\n' "$base" "$fingerprint" >"$work/.obraz-otisky-next"
mv -T "$work/.obraz-otisky-next" "$work/obraz-otisky"
