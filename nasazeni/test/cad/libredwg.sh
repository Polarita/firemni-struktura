#!/bin/bash
# Využije bezsíťovou sestavovací instanci s kompilátorem připraveným v bloku 7.
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
version=0.14
digest=62ebb73b984f865960f20ed26619ea5f8789d5e3fd088fa40a2598384da81275
archive=libredwg-$version.tar.xz
root=/var/cache/polarita-cad-test/libredwg
rev=$(sha256sum "$src/libredwg.sh" | cut -d' ' -f1)
out=$root/$rev
if [[ ${1:-} == --cesta ]]; then
    (cd "$out" && sha256sum --strict --status -c SHA256SUMS)
    printf '%s\n' "$out"
    exit 0
fi
[[ $# == 0 ]]
install -dm0755 "$root"
exec 7>"$root/.sestaveni"
flock 7
if [[ -d $out ]]; then
    (cd "$out" && sha256sum --strict --status -c SHA256SUMS)
    printf '%s\n' "$out"
    exit 0
fi
tmp=$(mktemp -d "$root/.priprava-XXXXXXXX")
vm=aigis-build-test
inside=(incus exec -T "$vm" --)
started=false
job=
finish() {
    if [[ $job =~ ^/var/tmp/polarita-libredwg-[[:alnum:]]{8}$ ]]; then
        "${inside[@]}" rm -r -- "$job"
    fi
    if [[ $started == true ]]; then incus stop "$vm"; fi
    if [[ -d $tmp ]]; then rm -r -- "$tmp"; fi
}
trap finish EXIT
if ! [[ -f $root/$archive ]] || ! (cd "$root" && echo "$digest  $archive" | sha256sum -c --status); then
    curl --proto '=https' --proto-redir '=https' -fsSL --retry 3 --max-time 180 \
        "https://github.com/LibreDWG/libredwg/releases/download/$version/$archive" -o "$tmp/$archive"
    (cd "$tmp" && echo "$digest  $archive" | sha256sum -c --status)
    mv -T "$tmp/$archive" "$root/$archive"
fi
exec 8>/run/polarita-test-zatez.lock
flock 8
exec 9>/var/cache/polarita-aigis-test/sestaveni.lock
flock 9
[[ $(incus config get "$vm" user.polarita.role) == "$vm" ]]
if [[ $(incus list "$vm" -f csv -c s) == STOPPED ]]; then incus start "$vm"; started=true; fi
"${inside[@]}" sh -ec 'test "$(ls /sys/class/net)" = lo; command -v gcc make >/dev/null'
job=$("${inside[@]}" runuser -u nobody -- mktemp -d /var/tmp/polarita-libredwg-XXXXXXXX)
# V sestavovací VM není xz. Ověřený archiv rozbalí neprivilegovaný účet z roury.
xz -dc -- "$root/$archive" | "${inside[@]}" runuser -u nobody -- tar -xf - -C "$job"
"${inside[@]}" runuser -u nobody -- nice -n 15 bash -se -- "$job" "$version" <<'BUILD' >&2
set -euo pipefail
cd "$1/libredwg-$2"
export LC_ALL=C CFLAGS='-O0 -g0'
./configure --disable-shared --enable-static --disable-docs --disable-bindings --disable-json >../configure.log 2>&1 || { tail -35 ../configure.log; exit 1; }
make -j1 -C src >../make.log 2>&1 && make -j1 -C programs dwg2dxf dxf2dwg >>../make.log 2>&1 || { tail -35 ../make.log; exit 1; }
for tool in dwg2dxf dxf2dwg; do "programs/$tool" --version; done
BUILD
install -dm0755 "$tmp/bin"
for tool in dwg2dxf dxf2dwg; do
    incus file pull "$vm$job/libredwg-$version/programs/$tool" "$tmp/bin/$tool"
    chmod 0755 "$tmp/bin/$tool"
done
incus file pull "$vm$job/libredwg-$version/COPYING" "$tmp/bin/COPYING"
(cd "$tmp/bin" && sha256sum dwg2dxf dxf2dwg COPYING >SHA256SUMS)
mv -T "$tmp/bin" "$out"
printf '%s\n' "$out"
