#!/bin/sh
set -eu
test "$(hostname -s)" = polarita-hq
test "$(systemd-detect-virt)" = kvm
src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
binary=${1:?cesta k sestavenemu programu portal}
name=reditelstvi-test
test -x "$binary"
if ! incus info "$name" >/dev/null 2>&1; then
    incus launch images:alpine/3.24 "$name" -p default -p app_internal -c boot.autostart=true -c user.polarita.role="$name"
fi
test "$(incus config get "$name" user.polarita.role)" = "$name"
if ! incus config device get "$name" portal listen >/dev/null 2>&1; then
    incus config device add "$name" portal proxy listen=tcp:127.0.0.1:18182 connect=tcp:127.0.0.1:8080
fi
test "$(incus config device get "$name" portal listen)" = tcp:127.0.0.1:18182
umask 077
install -d -m 700 /srv/polarita/vault/test-login
cd /srv/polarita/vault/test-login
# Link publikuje až úplný soubor, také při dvou souběžných instalacích.
python3 - <<'PY'
import os, secrets, tempfile
from pathlib import Path
target = Path('heslo')
if not target.exists():
    def word():
        return ''.join(secrets.choice('bcdfghjklmnprstvz') + secrets.choice('aeiou') for _ in range(3))
    with tempfile.NamedTemporaryFile(mode='w', dir='.', delete=False) as f:
        print('-'.join(word() for _ in range(4)), file=f)
    try:
        os.link(f.name, target)
    except FileExistsError:
        pass
    finally:
        os.unlink(f.name)
PY
test -s heslo
tr -d '\n' <heslo | sha256sum | cut -d' ' -f1 | incus file push --mode=0444 - "$name/etc/polarita-test.sha256"
incus exec "$name" -- mkdir -p /usr/local/share
incus file push --mode=0644 "$src/../../balicky/S3-konfigurator-a-tarify/konfigurator.html" "$name/usr/local/share/konfigurator.html"
incus file push --mode=0755 "$binary" "$name/usr/local/bin/polarita-portal.new"
incus exec "$name" -- mv /usr/local/bin/polarita-portal.new /usr/local/bin/polarita-portal
incus file push --mode=0755 "$src/portal.init" "$name/etc/init.d/polarita-portal"
incus exec "$name" -- rc-update add polarita-portal default
incus exec "$name" -- rc-service polarita-portal restart
curl -fsS --retry 4 --retry-connrefused -o /dev/null http://127.0.0.1:18182/
