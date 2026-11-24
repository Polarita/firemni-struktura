#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
name=aigis-build-test
image=0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50
root=/var/cache/polarita-aigis-test
install -d -m 0755 "$root/vstup"
exec 9>"$root/sestaveni.lock"
flock 9
out=/srv/polarita/infra/gitea-runner-test/podklady/aigis
recipe=$(cd "$src" && sha256sum podklady.py build.sh sestav.sh kontrola.py zkouska.py | sha256sum | cut -d' ' -f1)
if [[ -L $out/current && $(readlink "$out/current") == "$recipe" ]] && (cd "$out/$recipe" && sha256sum --check --status SHA256SUMS); then
    exit 0
fi
python3 "$src/podklady.py" "$root/vstup"
if ! incus info "$name" >/dev/null 2>&1; then
    incus init "local:$image" "$name" -p default -p sandbox_airgap \
        -c user.polarita.role="$name" -c boot.autostart=false -c limits.cpu=1 -c limits.memory=1800MiB \
        -c limits.cpu.priority=0 -c limits.disk.priority=0
fi
[[ $(incus config get "$name" user.polarita.role) == "$name" && $(incus config get "$name" volatile.base_image) == "$image" ]]
if ! incus config device list "$name" | grep -Fxq vstup; then
    incus config device add "$name" vstup disk source="$root/vstup" path=/opt/polarita-vstup readonly=true
fi
[[ $(incus config device get "$name" vstup source) == "$root/vstup" && $(incus config device get "$name" vstup readonly) == true ]]
if [[ $(incus list "$name" -f csv -c s) == STOPPED ]]; then incus start "$name"; fi
guest=(incus exec -T "$name" --)
"${guest[@]}" sh -ec 'test "$(ls /sys/class/net)" = lo'
bash "$src/../../incus/balicky.sh" "$name" cargo=1.93.1ubuntu1 rustc=1.93.1ubuntu1 g++=4:15.2.0-5ubuntu1 make=4.4.1-3 pkg-config=2.5.1-4
incus file push --mode 0755 "$src/build.sh" "$name/usr/local/bin/polarita-build-aigis"
if [[ ${1:-} == --priprav ]]; then exit 0; fi
"${guest[@]}" nice -n 16 /usr/local/bin/polarita-build-aigis
incus file push --mode 0644 "$src/kontrola.py" "$name/opt/polarita-aigis/kontrola.py"
incus file push --mode 0644 "$src/zkouska.py" "$name/opt/polarita-aigis/zkouska.py"
"${guest[@]}" runuser -u pol-build -- python3 /opt/polarita-aigis/zkouska.py
install -d -m 0755 "$out"
pending=$(mktemp -d "$out/.balik-XXXXXXXX")
trap 'if [[ -d $pending ]]; then rm -r -- "$pending"; fi' EXIT
chmod 0755 "$pending"
install -d -m 0755 "$pending/lib"
install -m 0644 "$src/kontrola.py" "$pending/kontrola.py"
install -m 0644 "$root/vstup/LICENSE-kuzu" "$pending/LICENSE-kuzu"
for file in aigiscode lib/libkuzu.so LICENSE-aigiscode; do
    incus file pull "$name/opt/polarita-aigis/$file" "$pending/$file"
done
(cd "$pending" && sha256sum aigiscode lib/libkuzu.so LICENSE-aigiscode LICENSE-kuzu kontrola.py >SHA256SUMS)
if [[ -d $out/$recipe ]]; then
    cmp "$pending/SHA256SUMS" "$out/$recipe/SHA256SUMS"
    (cd "$out/$recipe" && sha256sum -c --status SHA256SUMS)
else
    mv -T "$pending" "$out/$recipe"
fi
# Konstantní cesty v RPATH a v runneru vždy odkazují do jediné úplné revize.
for file in aigiscode lib LICENSE-aigiscode LICENSE-kuzu kontrola.py SHA256SUMS; do
    if [[ ! -L $out/$file ]]; then ln -s "current/$file" "$out/$file"; fi
    [[ $(readlink "$out/$file") == "current/$file" ]]
done
ln -sfn "$recipe" "$out/.current-next"
mv -Tf "$out/.current-next" "$out/current"
incus stop "$name"
