#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
umask 022
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/vikunja-test
data=/srv/polarita/data/vikunja-test
cache=/var/cache/polarita-vikunja-test
install -dm0755 "$work/bin" "$work/tofu"
install -dm0700 "$cache"
exec 9>"$work/.instalace"
flock 9
[[ $(findmnt -no SOURCE --mountpoint /srv/polarita/data) == polarita_zfs/data ]]
if ! zfs list -Ho name polarita_zfs/data/vikunja-test >/dev/null 2>&1; then
    [[ ! -e $data ]]
    zfs create -o mountpoint="$data" -o devices=off -o setuid=off -o exec=off polarita_zfs/data/vikunja-test
fi
[[ $(findmnt -no SOURCE --mountpoint "$data") == polarita_zfs/data/vikunja-test ]]
[[ $(zfs get -Ho value encryptionroot polarita_zfs/data/vikunja-test) == polarita_zfs ]]
name=vikunja-v2.8.0-linux-amd64
archive=$name-full.zip
sha=0b6ba2934bd432eefaa4209b0f96d20b7f7cd7f7be0269dd79071979c4363423
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
cd "$cache"
if ! [[ -f $archive ]] || ! echo "$sha  $archive" | sha256sum --check --status; then
    curl --proto '=https' -fLsS --retry 3 --max-time 200 "https://github.com/go-vikunja/vikunja/releases/download/v2.8.0/$archive" -o "$archive.next"
    echo "$sha  $archive.next" | sha256sum --check --status
    mv -T "$archive.next" "$archive"
fi
python3 - "$archive" "$name" "$work/bin" <<'PY'
import hashlib, os, shutil, sys, tempfile
from pathlib import Path
from zipfile import ZipFile
archive, name, folder = sys.argv[1:]
dst = Path(folder)/"vikunja"
with ZipFile(archive) as z:
    checksum, filename = z.read(name+".sha256").decode().split()
    if filename.lstrip("*") != name:
        raise ValueError("Kontrolní součet patří jinému programu.")
    if dst.is_file():
        with dst.open("rb") as f:
            if hashlib.file_digest(f,"sha256").hexdigest() == checksum:
                sys.exit(0)
    with tempfile.NamedTemporaryFile(dir=folder, delete=False) as f:
        pending=Path(f.name)
    try:
        with z.open(name) as source, pending.open("wb") as target:
            shutil.copyfileobj(source,target)
            target.flush()
            os.fsync(target.fileno())
        with pending.open("rb") as f:
            if hashlib.file_digest(f,"sha256").hexdigest() != checksum:
                raise ValueError("Obsah spustitelného souboru neodpovídá vydání.")
        pending.chmod(0o755)
        pending.replace(dst)
    finally:
        pending.unlink(missing_ok=True)
PY
cd "$work/tofu"
install -m0644 "$src/vikunja.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
bash "$src/../incus/tofu-init.sh"
tofu validate
tofu plan -input=false -out="$tmp/plan"
tofu show -json "$tmp/plan" | python3 -c '
import json,sys
for item in json.load(sys.stdin).get("resource_changes",[]):
    actions=item["change"]["actions"]
    if actions in (["no-op"],["read"]): continue
    if item["address"]!="incus_instance.vikunja" or actions not in (["create"],["update"]):
        sys.exit("Neočekávaná změna "+item["address"])'
tofu apply -input=false "$tmp/plan"
incus exec -T vikunja-test -- bash -ec '
    for i in {1..60}; do
        if test -S /run/systemd/private && mountpoint -q /var/lib/vikunja; then break; fi
        sleep 1
    done
    mountpoint -q /var/lib/vikunja
    /opt/polarita-vikunja/vikunja version | tee /run/polarita-vikunja-verze
    grep -F "v2.8.0" /run/polarita-vikunja-verze'
tofu plan -input=false -detailed-exitcode
