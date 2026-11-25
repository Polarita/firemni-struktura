#!/bin/bash
# Stabilní editor a displej pro jednorázové bezsíťové zkoušky schémat.
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
vm=qet-nastroje-test
image=0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50
cache=/var/cache/polarita-qet-test
file=QElectroTech_0.100.0-r8590-x86_64.AppImage
digest=ff9ff8a3ae0a9caaec7ae5d139308fc8e11f89b1d3f2518e75aa8bf050a6a8d6
install -dm0755 "$cache"
exec 9>"$cache/.priprava"
flock 9
cd "$cache"
if ! echo "$digest  $file" | sha256sum -c --status; then
    tmp=$(mktemp .qet-XXXXXXXX)
    trap 'rm -f -- "$tmp"' EXIT
    curl -fsSL --proto '=https' --proto-redir '=https' --retry 3 --max-time 300 \
        "https://github.com/qelectrotech/qelectrotech-source-mirror/releases/download/0.100/$file" -o "$tmp"
    echo "$digest  $tmp" | sha256sum -c --status
    chmod 0755 "$tmp"
    mv -T "$tmp" "$file"
    trap - EXIT
fi
exec 8>/run/polarita-test-zatez.lock
flock 8
if ! incus info "$vm" >/dev/null 2>&1; then
    incus init "local:$image" "$vm" -p default -p sandbox_airgap \
        -c user.polarita.role="$vm" -c boot.autostart=false -c limits.cpu=1 -c limits.memory=768MiB \
        -c limits.cpu.priority=0 -c limits.disk.priority=0
fi
[[ $(incus config get "$vm" user.polarita.role) == "$vm" && $(incus config get "$vm" volatile.base_image) == "$image" ]]
if [[ $(incus list "$vm" -c s -f csv) == STOPPED ]]; then incus start "$vm"; fi
trap 'incus stop "$vm"' EXIT
run=(incus exec -T "$vm" --)
"${run[@]}" sh -ec 'test "$(ls /sys/class/net)" = lo'
bash "$src/../incus/balicky.sh" "$vm" xvfb=2:21.1.22-1ubuntu1.3 xdotool=1:3.20160805.1-5.1build1 \
    xauth=1:1.1.2-1.1build1 libqt5gui5t64=5.15.18+dfsg-1ubuntu1 libxcb-xinerama0=1.17.0-2ubuntu1 \
    libxcb-cursor0=0.1.6-1 fonts-dejavu-core=2.37-8build1 qelectrotech-examples=1:0.9-3build1
dir=/opt/polarita/qet-$digest
if ! "${run[@]}" test -x "$dir/AppRun"; then
    job=$("${run[@]}" runuser -u nobody -- mktemp -d /var/tmp/polarita-qet-XXXXXXXX)
    [[ $job =~ ^/var/tmp/polarita-qet-[a-zA-Z0-9]{8}$ ]]
    incus file push --mode=0755 "$file" "$vm$job/qet.AppImage"
    "${run[@]}" bash -se -- "$job" "$digest" "$dir" <<'EXTRACT'
set -euo pipefail
cd "$1"
trap 'rm -r -- "$1"' EXIT
echo "$2  qet.AppImage" | sha256sum -c --status
runuser -u nobody -- sh -c 'umask 022; exec ./qet.AppImage --appimage-extract' >/dev/null
test -x squashfs-root/AppRun
chown -Rh root:root squashfs-root
install -dm0755 /opt/polarita
mv -T squashfs-root "$3"
EXTRACT
fi
# Starší šablona mohla rozbalit veřejný obraz pod umask 077 a teprve potom změnit vlastníka.
"${run[@]}" bash -ec '
    set -eu
    dir=$1
    [[ -d $dir && ! -L $dir && $(stat -c %u "$dir") == 0 ]]
    if ! runuser -u nobody -- test -x "$dir/AppRun"; then
        find "$dir" -type d -exec chmod a+rx {} +
        find "$dir" -type f -exec chmod a+rX {} +
    fi
    runuser -u nobody -- test -x "$dir/AppRun"
' -- "$dir"
"${run[@]}" ln -sfn "$dir" /opt/polarita/qet
"${run[@]}" test -s /usr/share/qelectrotech/examples/741.qet
