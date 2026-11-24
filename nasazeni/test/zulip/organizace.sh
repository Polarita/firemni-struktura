#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/zulip-test/conf
exec 9>/srv/polarita/infra/zulip-test/.organizace
flock 9
inside=(incus exec -T zulip-test --)
names=$(mktemp -p "$work" pozice.XXXXXXXX)
trap 'rm -f -- "$names"' EXIT
python3 "$src/../paperclip/pozice.py" --zulip >"$names"
chmod 0644 "$names"
mv -T "$names" "$work/pozice.json"
install -m 0644 "$src/organizace.py" "$work/"
# Může se jednat o první migraci serveru. Čekáme na připravenost nativního aplikačního procesu.
for i in {1..100}; do
    if "${inside[@]}" supervisorctl status zulip-django | grep -q RUNNING; then break; fi
    sleep 6
done
"${inside[@]}" supervisorctl status zulip-django | grep -q RUNNING
"${inside[@]}" runuser -u zulip -- /home/zulip/deployments/current/manage.py shell \
    -c 'exec(compile(open("/etc/polarita-zulip/organizace.py").read(),"/etc/polarita-zulip/organizace.py","exec"))'
