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
python3 - >"$names" <<'PYZ'
import json
from pathlib import Path
plan = json.loads(Path("/srv/polarita/data/paperclip/pozice.json").read_bytes())
if not plan.get("zdroj_gitea"):
    raise SystemExit("Chybí soupis botů z ověřené revize Gitey")
print(json.dumps({a["id"]: f'{a["name"]} (ai {a["id"]})' for a in plan["agents"]}, ensure_ascii=False))
PYZ
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
