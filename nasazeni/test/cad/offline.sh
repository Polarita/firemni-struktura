#!/bin/bash
# Knihovny se stáhnou v ředitelství, výkres se otevře až v bezsíťové pracovní VM.
set -euo pipefail
src=$(cd "$(dirname "$0")" && pwd)
revision=$(cd "$src" && sha256sum offline.sh libredwg.sh kola.lock prevod.py mereni.py zkouska.py vzor.ifc | sha256sum | cut -d' ' -f1)
if [[ ${1:-} == --revize ]]; then echo "$revision"; exit 0; fi
[[ $# == 0 && $EUID == 0 && $(hostname -s) == polarita-hq ]]
vm=karantena-test
run=(incus exec -T "$vm" --)
key=$(sha256sum "$src/kola.lock" | cut -d' ' -f1)
cache=/var/cache/polarita-cad-test/$key
bash "$src/libredwg.sh"
dwg=$(bash "$src/libredwg.sh" --cesta)
exec 9>/srv/polarita/infra/karantena-test/.instalace
flock 9
python3 "$src/kola.py" "$cache"
exec 8>/run/polarita-test-zatez.lock
flock 8
[[ $(incus config get "$vm" user.polarita.role) == "$vm" && $(incus list "$vm" -c s -f csv) == STOPPED ]]
incus start "$vm"
tmp=
job=
finish() {
    if [[ -n $tmp ]]; then rm -rf -- "$tmp"; fi
    if [[ $job =~ ^/var/tmp/polarita-vykres-[A-Za-z0-9]{8}$ ]]; then
        "${run[@]}" rm -rf -- "$job" || echo 'Dočasný výkres zůstal uvnitř pracovní VM.' >&2
    fi
    python3 "$src/../karantena/zpracovani.py" --zastav-vm </dev/null || exit 1
}
trap finish EXIT
for i in {1..120}; do
    if "${run[@]}" true 2>/dev/null; then break; fi
    sleep 1
done
"${run[@]}" bash -ec '[[ $(ls /sys/class/net) == lo && $(uname -m) == x86_64 ]]'
base=/opt/polarita/cad
"${run[@]}" install -dm0755 "$base/$key"
if ! "${run[@]}" test -d "$base/$key/lib"; then
    inbox=$("${run[@]}" mktemp -d /var/tmp/polarita-cad-XXXXXXXX)
    tar -cf - -C "$cache" . | "${run[@]}" tar xf - -C "$inbox"
    incus file push "$src/kola.lock" "$vm$inbox/kola.lock"
    "${run[@]}" bash -se -- "$inbox" "$base/$key" <<'INSTALL'
set -euo pipefail
cd "$1"
tmp=$(mktemp -d "$2/.lib-XXXXXXXX")
trap 'rm -rf -- "$tmp" "$1"' EXIT
# Ověření v cílové VM probíhá ještě před načtením samotného pipu.
while IFS= read -r line; do
    name=${line##*/}; file=${name%#*}; sum=${line##*#sha256=}
    printf '%s  %s\n' "$sum" "$file" >>SHA256SUMS
    printf './%s --hash=sha256:%s\n' "$file" "$sum" >>requirements.txt
done <kola.lock
sha256sum --check --strict --status SHA256SUMS
pip=(pip-*.whl)
[[ ${#pip[@]} == 1 ]]
PYTHONPATH="$PWD/${pip[0]}" python3 -m pip --isolated --disable-pip-version-check install --no-index \
    --no-cache-dir --ignore-installed --no-compile --only-binary=:all: --require-hashes --target "$tmp" -r requirements.txt >&2
chmod 0755 "$tmp"
mv -T "$tmp" "$2/lib"
INSTALL
fi
code=$base/$key/$revision
"${run[@]}" install -dm0755 "$code"
if ! "${run[@]}" test -d "$code/libredwg"; then
    target=$("${run[@]}" mktemp -d "$code/.libredwg-XXXXXXXX")
    tar -C "$dwg" -cf - dwg2dxf dxf2dwg COPYING SHA256SUMS | "${run[@]}" tar -xf - -C "$target"
    "${run[@]}" sh -ec 'cd "$1"; sha256sum --strict --status -c SHA256SUMS; chmod 0755 .; mv -T "$1" "$2"' sh "$target" "$code/libredwg"
fi
"${run[@]}" sh -ec 'cd "$1"; sha256sum --strict --status -c SHA256SUMS' sh "$code/libredwg"
for file in prevod.py mereni.py zkouska.py vzor.ifc; do
    incus file push --mode=0644 "$src/$file" "$vm$code/$file.next"
    "${run[@]}" mv -T "$code/$file.next" "$code/$file"
done
job=$("${run[@]}" runuser -u nobody -- mktemp -d /var/tmp/polarita-vykres-XXXXXXXX)
[[ $job =~ ^/var/tmp/polarita-vykres-[A-Za-z0-9]{8}$ ]]
"${run[@]}" runuser -u nobody -- env HOME="$job" PATH="$code/libredwg:/usr/bin:/bin" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$base/$key/lib" \
    OPENBLAS_NUM_THREADS=1 python3 "$code/zkouska.py" "$job"
proof=/srv/polarita/workspace/dukazy/blok-10
install -dm0750 "$proof"
tmp=$(mktemp -d "$proof/.cad-XXXXXXXX")
doklady=(vzor.dxf vzor.ifc vzor.dwg vzor-dxf.pdf vzor-ifc.pdf vzor-dwg.pdf kalibrace.json mereni.json)
for file in "${doklady[@]}"; do
    incus file pull "$vm$job/$file" "$tmp/$file"
done
"${run[@]}" rm -rf -- "$job"
job=
(cd "$tmp" && sha256sum "${doklady[@]}" > SHA256SUMS)
# Jedna revize a její otisky se zveřejní společně.
if [[ -d $proof/cad-$revision ]]; then
    (cd "$proof/cad-$revision" && sha256sum --strict --status -c SHA256SUMS)
else
    mv -T "$tmp" "$proof/cad-$revision"
fi
"${run[@]}" bash -se -- "$base/$key/lib" "$code" <<'ENTRY'
set -euo pipefail
for pair in polarita-cad-pdf:prevod polarita-cad-mereni:mereni; do
    name=${pair%:*}
    tmp=$(mktemp "/usr/local/bin/.$name-XXXXXXXX")
    printf '#!/bin/sh\nexport PYTHONPATH=%s PATH=%s/libredwg:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1\nexec python3 %s "$@"\n' "$1" "$2" "$2/${pair#*:}.py" >"$tmp"
    chmod 0755 "$tmp"
    mv -T "$tmp" "/usr/local/bin/$name"
done
ENTRY
echo "Vektorová PDF a zdrojové výkresy jsou v $proof/cad-$revision."
