#!/bin/bash
# Vnější Incus drží jedinou firemní VM a její datový svazek v existujícím projektu.
set -euo pipefail
[[ $EUID == 0 && $(hostname -s) == ejpovice ]]
exec 9>/run/lock/polarita-zalozeni-vm.lock
flock 9
inc=(incus --project polarita)
vm=polarita-hq
disk=polarita-hq-data
pool=zrcadlo
image=2383d18cd3fae40cfff69b2c2de9d893c054db261e93cd24455f378ed1b31c5d
"${inc[@]}" project show polarita >/dev/null
[[ $(incus query "/1.0/storage-pools/$pool" | python3 -c 'import json,sys;print(json.load(sys.stdin)["driver"])') == ceph ]]
instances=$("${inc[@]}" list --format csv -c n)
if ! grep -Fxq "$vm" <<<"$instances"; then
    if "${inc[@]}" storage volume show "$pool" "$disk" >/dev/null 2>&1; then
        echo 'Samostatný datový svazek již existuje. Jeho vlastnictví nelze přiřadit nové VM.' >&2
        exit 1
    fi
    if ! "${inc[@]}" image info "local:$image" >/dev/null 2>&1; then
        "${inc[@]}" image copy "images:$image" local: --vm
    fi
    "${inc[@]}" init "local:$image" "$vm" --vm --target ejpovice -p default --storage "$pool" \
        --network incusbr0 -d root,size=40GiB -c limits.cpu=2 -c limits.memory=6GiB \
        -c user.polarita.zalozeni=instalator-test
fi
info=$(incus query "/1.0/instances/$vm?project=polarita")
python3 -c '
import json,sys
vm=json.load(sys.stdin)
root=vm["expanded_devices"]["root"]
if (vm["name"],vm["location"],vm["type"],root["pool"],root["path"]) != (
        "polarita-hq","ejpovice","virtual-machine","zrcadlo","/"):
    sys.exit("Nesouhlasí umístění, druh VM nebo její systémový disk")
' <<<"$info"
if [[ $("${inc[@]}" config get "$vm" user.polarita.zalozeni) == instalator-test ]]; then
    owner=$("${inc[@]}" config get "$vm" volatile.uuid)
    [[ $owner =~ ^[0-9a-f-]{36}$ ]]
    if ! "${inc[@]}" storage volume show "$pool" "$disk" >/dev/null 2>&1; then
        "${inc[@]}" storage volume create "$pool" "$disk" --type block size=48GiB "user.polarita.vm=$owner"
    fi
    [[ $("${inc[@]}" storage volume get "$pool" "$disk" user.polarita.vm) == "$owner" ]]
    devices=$("${inc[@]}" config device list "$vm")
    if ! grep -Fxq data <<<"$devices"; then "${inc[@]}" storage volume attach "$pool" "$disk" "$vm" data; fi
    if ! grep -Fxq tpm0 <<<"$devices"; then "${inc[@]}" config device add "$vm" tpm0 tpm; fi
    "${inc[@]}" config set "$vm" boot.autostart=true
fi
incus query "/1.0/instances/$vm?project=polarita" | python3 -c '
import json,sys
devices=json.load(sys.stdin)["expanded_devices"]
data=devices.get("data",{})
if (data.get("type"),data.get("pool"),data.get("source")) != ("disk","zrcadlo","polarita-hq-data"):
    sys.exit("Datový disk neodpovídá projektu")
if not any(d["type"]=="tpm" for d in devices.values()):
    sys.exit("VM postrádá vTPM")
'
state=$(incus query "/1.0/instances/$vm/state?project=polarita" | python3 -c 'import json,sys;print(json.load(sys.stdin)["status"])')
case "$state" in
    Running) ;;
    Stopped) "${inc[@]}" start "$vm" ;;
    *) echo "Neočekávaný stav VM: $state" >&2; exit 1 ;;
esac
timeout 240 bash -c 'until [[ $(incus exec -T --project polarita polarita-hq -- hostname -s 2>/dev/null) == polarita-hq ]]; do sleep 3; done'
echo 'V projektu polarita běží na Ejpovicích VM polarita-hq s vyhrazeným datovým svazkem a vTPM.'
