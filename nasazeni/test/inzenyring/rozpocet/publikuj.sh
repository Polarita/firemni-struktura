#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
cache=/var/cache/polarita-rozpocet-test
install -d -m0755 "$cache"
exec 8>/run/polarita-rozpocet-test.lock
flock 8
lib=$(bash "$src/nastroje.sh" "$cache")
schema=$cache/NZ-43151f01.xsd
case_id=$(cd "$src/.." && python3 -c 'from prijem import CASE; print(CASE)')
[[ $case_id =~ ^[a-f0-9-]{36}$ ]]
work=$(mktemp -d /var/tmp/polarita-rozpocet-XXXXXXXX)
trap 'rm -r -- "$work"' EXIT
install -m0644 "$src"/*.py "$src/vykaz-test.json" "$work/"
chmod 0755 "$work"
install -d -m0700 -o nobody "$work/vysledek"
out=$work/vysledek
run=(runuser -u nobody -- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$lib" POLARITA_XC4_SCHEMA="$schema" python3)
"${run[@]}" "$work/test_rozpocet.py"
cmd=("${run[@]}" "$work/rozpocet.py" --schema "$schema")
"${cmd[@]}" z-vykazu "$work/vykaz-test.json" "$out/nabidka.xc4"
"${cmd[@]}" do-xlsx "$out/nabidka.xc4" "$out/nabidka.xlsx"
"${cmd[@]}" do-xc4 "$out/nabidka.xlsx" "$out/zpet.xc4"
cmp "$out/nabidka.xc4" "$out/zpet.xc4"
"${cmd[@]}" over "$out/zpet.xc4"
root=/opt/polarita-inzenyring-test/rozpocty/$case_id
rev=$(cd "$src" && sha256sum *.py vykaz-test.json kola.lock | sha256sum | cut -d' ' -f1)
guest=(incus exec -T postgres-test --)
"${guest[@]}" install -d -m0755 "$root"
if ! "${guest[@]}" test -d "$root/$rev"; then
    stage=$("${guest[@]}" mktemp -d "$root/.priprava-XXXXXXXX")
    tar -C "$out" --mode=0644 --owner=0 --group=0 -cf - nabidka.xc4 nabidka.xlsx | "${guest[@]}" tar -xf - -C "$stage"
    (cd "$out" && sha256sum nabidka.xc4 nabidka.xlsx) | "${guest[@]}" tee "$stage/SHA256SUMS" >/dev/null
    "${guest[@]}" bash -ec 'cd "$1"; sha256sum -c SHA256SUMS; chmod 0755 .; mv -T "$1" "$2"' -- "$stage" "$root/$rev"
fi
"${guest[@]}" bash -ec 'cd "$1/$2"; sha256sum -c SHA256SUMS; cd ..; ln -sfn "$2" .current.next; mv -Tf .current.next current' -- "$root" "$rev"
