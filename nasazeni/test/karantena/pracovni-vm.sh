#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == karantena-test && $(ls /sys/class/net) == lo ]]
id karantena >/dev/null 2>&1 || useradd --uid 17304 --user-group --create-home --shell /bin/bash karantena
[[ $(id -u karantena) == 17304 && $(id -g karantena) == 17304 ]]
# Podman bez roota používá uživatelský namespace a vlastní podřízené rozsahy UID/GID.
grep -q '^karantena:' /etc/subuid
grep -q '^karantena:' /etc/subgid
install -d -m 0755 /opt/polarita
cat > /etc/tmpfiles.d/polarita-karantena.conf <<'CONF'
d /run/user/17304 0700 karantena karantena -
CONF
systemd-tmpfiles --create /etc/tmpfiles.d/polarita-karantena.conf
loginctl enable-linger karantena
systemctl start user@17304.service
cat >/opt/polarita/pamet.sh <<'MEM'
#!/bin/bash
set -euo pipefail
modprobe zram
if ! grep -q '^/dev/zram0 ' /proc/swaps; then
    if [[ $(cat /sys/block/zram0/disksize) == 0 ]]; then
        echo 1610612736 > /sys/block/zram0/disksize
        mkswap /dev/zram0 >/dev/null
    fi
    swapon -p 100 /dev/zram0
fi
MEM
chmod 0755 /opt/polarita/pamet.sh
cat > /etc/systemd/system/polarita-karantena-pamet.service <<'UNIT'
[Unit]
Description=Komprimovaná pracovní paměť pro offline konverzi
After=systemd-modules-load.service
[Service]
Type=oneshot
ExecStart=/opt/polarita/pamet.sh
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now polarita-karantena-pamet.service
for mount in /mnt/karantena-in /mnt/karantena-out /mnt/clamav-db; do mountpoint -q "$mount"; done
dpkg-query -W -f='${Version}\n' dangerzone-full
cd /home/karantena
runuser -u karantena -- env XDG_RUNTIME_DIR=/run/user/17304 podman info --format '{{.Host.Security.Rootless}}' | grep -Fx true
# Podepsaný převodní obraz z balíčku připrav už při instalaci, bez spuštění přílohy.
runuser -u karantena -- env XDG_RUNTIME_DIR=/run/user/17304 python3 - <<'PY'
from dangerzone.updater import installer
from dangerzone.settings import Settings

Settings().set("updater_check_all", False, autosave=True)
installer.install()
if installer.get_installation_strategy() != installer.Strategy.DO_NOTHING:
    raise RuntimeError("Offline obraz Dangerzone není připravený")
print("Podepsaný obraz Dangerzone je připravený pod účtem pracovníka.")
PY
# První přemapování vlastníků obrazu v režimu Podman nomap trvá na vnořeném disku déle než konverze přílohy.
# Opravdovou přílohu přijímáme až po vytvoření tohoto podkladu na instalačním vzoru bez sítě.
runuser -u karantena -- env XDG_RUNTIME_DIR=/run/user/17304 bash -se <<'READY'
set -euo pipefail
digest=sha256:f0c2923b45cc40553d3a86956535b66b8da5a56d1cb8e9b2370298c191dd8176
image="ghcr.io/freedomofpress/dangerzone/v1@$digest"
podman image exists "$image"
cache="polarita-podklad-${digest:7:12}"
if ! podman container exists "$cache"; then
    podman create --pull=never --network=none --cap-drop=all --security-opt=no-new-privileges \
        --userns=nomap --read-only --name "$cache" "$image" /bin/true </dev/null >/dev/null
fi
expected=$(podman image inspect --format '{{.Id}}' "$image")
actual=$(podman container inspect --format '{{.Image}}' "$cache")
[[ ${actual#sha256:} == "${expected#sha256:}" ]]
state=$HOME/.local/state/polarita-karantena
mkdir -p -m 0700 "$state"
stamp="$state/${cache}.pdf"
if ! test -s "$stamp" || ! qpdf --check "$stamp" >/dev/null; then
    stage=$(mktemp -d "$state/vzor-XXXXXXXX")
    trap 'rm -rf -- "$stage"' EXIT
    dangerzone-cli --output-filename "$stage/vzor.pdf" /usr/share/dangerzone/dummy_document.pdf </dev/null
    qpdf --check "$stage/vzor.pdf" >/dev/null
    mv "$stage/vzor.pdf" "$stamp"
fi
echo 'První konverze vzoru na tomto obrazu byla ověřena před otevřením fronty.'
READY
