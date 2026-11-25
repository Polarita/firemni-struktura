#!/bin/bash
# Testuje pouze vlastní instanci testovacího trezoru uvnitř polarita-hq.
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
work=/srv/polarita/infra/openbao-test
[[ ! -e $work/uzamceno ]]
exec 8>"$work/.zkouska-startu"
flock 8
# Dobíhající klient nesmí přijít o trezor uprostřed vydávání přístupu.
exec 9>"$work/.install-lock"
flock 9
"$work/bin/sprava.sh" uzamknout
trap '"$work/bin/sprava.sh" odemknout' EXIT
systemctl start polarita-openbao-start.service
if incus exec openbao-test -- systemctl is-active --quiet openbao; then exit 1; fi
incus restart openbao-test
for i in {1..60}; do
    if incus exec openbao-test -- test -S /run/systemd/private; then break; fi
    sleep 1
done
incus exec openbao-test -- test ! -e /run/secrets/polarita-test
incus exec openbao-test -- test ! -e /run/openbao-seal/klíč
"$work/bin/sprava.sh" odemknout
trap - EXIT
incus exec openbao-test -- test ! -e /run/openbao-seal/klíč
flock -u 9
systemctl start polarita-openbao-agenti.service
echo 'Restart trezoru odstranil tajemství z tmpfs. Úmyslný zámek vydržel. Po odemčení TPM každá připojená služba získala své údaje a ověřila shodu.'
