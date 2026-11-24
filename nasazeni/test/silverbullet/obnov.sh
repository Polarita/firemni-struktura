#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
work=/srv/polarita/infra/silverbullet-test
dst=/srv/polarita/data/silverbullet-test
[[ $(findmnt -no SOURCE --mountpoint "$dst") == polarita_zfs/data/silverbullet-test ]]
exec 8>"$work/.aktualizace"
flock 8
rev=$(python3 "$work/pohled.py")
[[ $rev =~ ^[0-9a-f]{40}$ ]]
state=$work/zobrazena-revize
if [[ -f $state && $(cat "$state") == "$rev" ]]; then exit 0; fi
inside=(incus exec -T silverbullet-test --)
"${inside[@]}" systemctl restart polarita-silverbullet
# Server drží index otevřeného prostoru. Novou revizi potvrdí až čtení přes jeho HTTP API.
"${inside[@]}" python3 - "$rev" <<'PY'
import hashlib
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

root = Path("/var/lib/polarita-znalosti/current")
assert root.readlink().name == sys.argv[1]
for entry in sorted(root.rglob("*.md")):
    url = "http://127.0.0.1:3000/pamet/.fs/" + quote(entry.relative_to(root).as_posix())
    expected = hashlib.sha256(entry.read_bytes()).digest()
    for attempt in range(15):
        try:
            with urlopen(url, timeout=4) as response:
                assert hashlib.sha256(response.read()).digest() == expected, entry.name
            break
        except OSError:
            if attempt == 14:
                raise
            time.sleep(1)
print("SilverBullet zpřístupnil ověřené stránky revize " + sys.argv[1])
PY
printf '%s\n' "$rev" >"$state.next"
mv -T "$state.next" "$state"
