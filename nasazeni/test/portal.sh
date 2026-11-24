#!/bin/sh
set -eu
test "$(hostname -s)" = polarita-hq
test "$(systemd-detect-virt)" = kvm
src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
binary=$(realpath "${1:?cesta k sestavenemu programu portal}")
name=reditelstvi-test
exec 8>/run/polarita-portal-instalace.lock
flock 8
test -x "$binary"
if ! incus info "$name" >/dev/null 2>&1; then
    incus launch images:alpine/3.24 "$name" -p default -p app_internal -c boot.autostart=true -c user.polarita.role="$name"
fi
test "$(incus config get "$name" user.polarita.role)" = "$name"
if ! incus config device list "$name" | grep -Fxq eth0; then
    incus config device override "$name" eth0 ipv4.address=10.239.32.10 security.ipv4_filtering=true security.mac_filtering=true
elif [ "$(incus config device get "$name" eth0 ipv4.address)" != 10.239.32.10 ] ||
     [ "$(incus config device get "$name" eth0 security.ipv4_filtering)" != true ] ||
     [ "$(incus config device get "$name" eth0 security.mac_filtering)" != true ]; then
    incus config device set "$name" eth0 ipv4.address=10.239.32.10 security.ipv4_filtering=true security.mac_filtering=true
fi
if ! incus exec "$name" -- ip -4 addr show dev eth0 | grep -q 'inet 10\.239\.32\.10/'; then
    incus restart "$name"
fi
umask 077
install -d -m 700 /srv/polarita/data/bootstrap-test/test-login
cd /srv/polarita/data/bootstrap-test/test-login
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
restart=/run/polarita-portal.reload
digest=$(tr -d '\n' <heslo | sha256sum | cut -d' ' -f1)
if ! printf '%s\n' "$digest" | incus exec -T "$name" -- cmp -s - /etc/polarita-test.sha256; then
    incus exec -T "$name" -- touch "$restart"
    printf '%s\n' "$digest" | incus file push --mode=0444 - "$name/etc/.polarita-test.sha256.next"
    incus exec -T "$name" -- mv -f /etc/.polarita-test.sha256.next /etc/polarita-test.sha256
fi
incus exec "$name" -- mkdir -p /usr/local/share
incus file push --mode=0644 "$src/../../balicky/S3-konfigurator-a-tarify/konfigurator.html" "$name/usr/local/share/.konfigurator.html.next"
incus exec -T "$name" -- mv -f /usr/local/share/.konfigurator.html.next /usr/local/share/konfigurator.html
for path in /usr/local/bin/polarita-portal /etc/init.d/polarita-portal; do
    case $path in
        /usr/local/bin/*) file=$binary ;;
        *) file=$src/portal.init ;;
    esac
    wanted=$(sha256sum "$file")
    actual=$(incus exec -T "$name" -- sh -c 'if test -x "$1"; then sha256sum "$1"; fi' -- "$path")
    if [ "${wanted%% *}" != "${actual%% *}" ]; then
        incus exec -T "$name" -- touch "$restart"
        incus file push --mode=0755 "$file" "$name$path.next"
        incus exec -T "$name" -- mv -f "$path.next" "$path"
    fi
done
incus exec -T "$name" -- rc-update add polarita-portal default
if incus exec -T "$name" -- test -f "$restart"; then
    incus exec -T "$name" -- rc-service polarita-portal restart
elif ! incus exec -T "$name" -- rc-service polarita-portal status; then
    incus exec -T "$name" -- rc-service polarita-portal start
fi
incus exec -T "$name" -- sh -ec 'for i in 1 2 3 4 5; do wget -qO /dev/null http://127.0.0.1:8080/ && exit 0; sleep 1; done; exit 1'
incus exec -T "$name" -- rm -f "$restart"
