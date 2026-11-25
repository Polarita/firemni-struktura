#!/bin/bash
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
bash "$src/priprav.sh"
exec 9>/var/cache/polarita-qet-test/.priprava
flock 9
exec 8>/run/polarita-test-zatez.lock
flock 8
template=qet-nastroje-test
[[ $(incus list "$template" -f csv -c s) == STOPPED ]]
name=qet-schema-$(cat /proc/sys/kernel/random/uuid)
incus copy --ephemeral --instance-only "$template" "$name" -c user.polarita.role=qet-schema-test
out=
finish() {
    if [[ -n $out && -d $out ]]; then rm -r -- "$out"; fi
    if [[ $(incus config get "$name" user.polarita.role) == qet-schema-test ]]; then incus delete -f "$name"; fi
}
trap finish EXIT
incus start "$name"
run=(incus exec -T "$name" --)
job=$("${run[@]}" runuser -u nobody -- mktemp -d /var/tmp/polarita-schema-XXXXXXXX)
[[ $job =~ ^/var/tmp/polarita-schema-[a-zA-Z0-9]{8}$ ]]
incus file push --mode=0644 "$src/zkouska.py" "$name$job/zkouska.py"
"${run[@]}" runuser -u nobody -- sh -ec 'cd "$1"; export HOME="$1" XDG_RUNTIME_DIR="$1/runtime" TMPDIR="$1/tmp" LANG=C.UTF-8; mkdir -m0700 "$XDG_RUNTIME_DIR" "$TMPDIR"; umask 077; touch "$1/Xauthority"; xvfb-run -f "$1/Xauthority" -a -s "-screen 0 1280x960x24 -nolisten tcp" python3 ./zkouska.py || { tail -25 editor.log >&2; exit 1; }' qet "$job"
proof=/srv/polarita/workspace/dukazy/blok-10
install -dm0750 "$proof"
out=$(mktemp -d "$proof/.qet-XXXXXXXX")
for file in vstup.qet ulozeno.qet; do incus file pull "$name$job/$file" "$out/$file"; done
(cd "$out" && sha256sum vstup.qet ulozeno.qet >SHA256SUMS)
# Každý průchod editoru může do souboru zapsat nový okamžik uložení.
result=$proof/qet-${name#qet-schema-}
mv -T "$out" "$result"
echo "Zdrojové a nativně uložené schéma s otisky jsou v $result."
