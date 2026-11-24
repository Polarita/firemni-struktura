#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/zulip-test/conf
inside=(incus exec -T zulip-test --)
python3 - "$src/../../../agenti-a-prompty" "$work/pozice.json" <<'PY'
import json,re,sys
from pathlib import Path
employees={}
for card in sorted(Path(sys.argv[1]).glob("[0-9][0-9][0-9][0-9][0-9]-*.md")):
    title=card.open(encoding="utf-8").readline()
    match=re.match(r"# Karta ai zaměstnance č\. (\d{5}): (.+?) \(ai\)",title)
    if not match or match[1] in employees or match[1]!=card.name[:5]:
        raise ValueError("Neznámá karta "+card.name)
    employees[match[1]]=f"{match[2]} (ai {match[1]})"
if len(employees)!=20:
    raise ValueError("Zulip vyžaduje úplný soupis firemních pozic")
out=Path(sys.argv[2])
temp=out.with_suffix(".next"); temp.write_text(json.dumps(employees,ensure_ascii=False)); temp.chmod(0o644); temp.replace(out)
PY
install -m 0644 "$src/organizace.py" "$work/"
# Může se jednat o první migraci serveru. Čekáme na připravenost nativního aplikačního procesu.
for i in {1..100}; do
    if "${inside[@]}" supervisorctl status zulip-django | grep -q RUNNING; then break; fi
    sleep 6
done
"${inside[@]}" supervisorctl status zulip-django | grep -q RUNNING
"${inside[@]}" runuser -u zulip -- /home/zulip/deployments/current/manage.py shell \
    -c 'exec(compile(open("/etc/polarita-zulip/organizace.py").read(),"/etc/polarita-zulip/organizace.py","exec"))'
