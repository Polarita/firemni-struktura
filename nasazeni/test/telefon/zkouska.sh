#!/bin/bash
set -euo pipefail
umask 077
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
revize=${1:?Zdrojová revize instalace TEST}
[[ $revize =~ ^[0-9a-f]{40}$ ]]
bash "$src/priprava.sh" >&2
exec 8>/run/polarita-telefon-test.lock
flock 8
inside=(incus exec -T asterisk-test --)
testdir=$("${inside[@]}" mktemp -d)
trap '"${inside[@]}" rm -r -- "$testdir"' EXIT
"${inside[@]}" chmod 0755 "$testdir"
tar -C "$src" -cf - hovor.py extensions.conf pjsip.conf | "${inside[@]}" tar -xf - -C "$testdir"
"${inside[@]}" install -d -m0700 -o asterisk -g asterisk "$testdir/nahravka"
"${inside[@]}" runuser -u asterisk -- python3 -B "$testdir/hovor.py" "$testdir/nahravka/hovor.wav"
expected=$("${inside[@]}" sha256sum "$testdir/nahravka/hovor.wav")
stage=$(mktemp -d /run/polarita-telefon-XXXXXXXX)
trap 'rm -r -- "$stage"; "${inside[@]}" rm -r -- "$testdir"' EXIT
incus file pull "asterisk-test$testdir/nahravka/hovor.wav" "$stage/hovor.wav"
otisk=${expected%% *}
[[ $otisk =~ ^[0-9a-f]{64}$ ]]
python3 "$src/../objekty/provoz.py" --testovaci-hovor "$stage/hovor.wav" "$otisk"
printf 'Revize zdrojů interního hovoru %s\n' "$revize"
