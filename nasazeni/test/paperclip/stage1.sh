#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")/../../../balicky/S2-eval-suite" && pwd)
inside=(incus exec -T paperclip-test --)
work=/srv/polarita/infra/paperclip-test
exec 9>"$work/.stage1"
flock 9
"${inside[@]}" install -d -m 0755 /opt/polarita-eval
for name in run_eval_suite.py reference_policy.py audio_fixtures.py eval_suite_polarita_extended.json; do
    incus file push --mode=0644 "$src/$name" paperclip-test/opt/polarita-eval/
done
"${inside[@]}" bash -se <<'INNER'
set -euo pipefail
mountpoint -q /var/lib/paperclip
dst=/var/lib/paperclip/eval
install -d -m 0750 -o paperclip-test -g paperclip-test "$dst"
report=$(mktemp -d -p "$dst" stage1.XXXXXXXX)
chown paperclip-test:paperclip-test "$report"
systemd-run --quiet --wait --pipe --collect -p User=paperclip-test -p Group=paperclip-test \
    -p NoNewPrivileges=true -p PrivateNetwork=true -p ProtectSystem=strict -p ProtectHome=true \
    -p "ReadWritePaths=$report" /usr/bin/python3 -B /opt/polarita-eval/run_eval_suite.py \
    --mode dry-run --suite base --no-history --out-dir "$report"
python3 - "$report" <<'PY'
from pathlib import Path
import json,sys
record, = Path(sys.argv[1]).glob("*.json")
data = json.loads(record.read_bytes())
if (data["mode"], data["suite"], data["evidence"], data["total"], data["passed"], data["failed"], data["verdict"]) != (
    "dry-run", "base", "REFERENCE_POLICY", 20, 20, 0, "VERIFIED_PASS"
):
    raise SystemExit("Stage 1 neprokázala požadovaných 20 případů")
print("Stage 1 prošla 20/20 bez sítě a bez volání modelu.")
PY
ln -sfn "${report##*/}" "$dst/.stage1-next"
mv -Tf "$dst/.stage1-next" "$dst/posledni-stage1"
INNER
# Provozní protokol je dostupný i v pracovním adresáři role ai-provoz.
workspace=/srv/polarita/workspace/ai-finops/eval-suite
install -d -m 0750 "$workspace"
pending=$(mktemp -d -p "$workspace" .stage1.XXXXXXXX)
trap 'rm -r -- "$pending"' EXIT
for ext in json md; do
    "${inside[@]}" runuser -u paperclip-test -- bash -ec '
        cd /var/lib/paperclip/eval/posledni-stage1
        files=(eval-report-dry-run-*."$1")
        [[ ${#files[@]} == 1 && -f ${files[0]} && ! -L ${files[0]} ]]
        cat -- "${files[0]}"
    ' -- "$ext" >"$pending/protokol.$ext"
done
stamp=$(python3 - "$pending/protokol.json" <<'PY'
from datetime import datetime
import json, sys
with open(sys.argv[1], encoding="utf-8") as stream:
    report = json.load(stream)
if (report["suite"], report["mode"], report["evidence"], report["passed"], report["total"],
    report["failed"], report["verdict"]) != ("base","dry-run","REFERENCE_POLICY",20,20,0,"VERIFIED_PASS"):
    raise SystemExit("Pracovní kopie nemá úplný výsledek Stage 1")
print(datetime.fromisoformat(report["started_utc"]).strftime("%Y%m%dT%H%M%S%fZ"))
PY
)
chmod 0750 "$pending"
chmod 0640 "$pending"/protokol.{json,md}
target=stage1-$stamp
if [[ -d "$workspace/$target" ]]; then
    cmp "$pending/protokol.json" "$workspace/$target/protokol.json"
    cmp "$pending/protokol.md" "$workspace/$target/protokol.md"
else
    mv -T "$pending" "$workspace/$target"
    trap - EXIT
fi
ln -sfn "$target" "$workspace/.posledni-stage1-next"
mv -Tf "$workspace/.posledni-stage1-next" "$workspace/posledni-stage1"
echo "Protokol Stage 1 je ve $workspace/$target."
