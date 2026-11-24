#!/bin/bash
# Při zkoušce je zařízením výhradně nový běžný soubor, při instalaci blok předaný Incusem.
set -euo pipefail
umask 077
owner=${1:?identita VM}
[[ $EUID == 0 && $(hostname -s) == polarita-hq && $owner =~ ^[0-9a-f-]{36}$ ]]
key=${CREDENTIALS_DIRECTORY:?}/polarita-zfs.key
[[ -s $key ]]
pool=polarita_zfs
base=/srv/polarita
disk=/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_incus_data
if [[ $# == 2 ]]; then
    testdir=$2
    [[ $testdir =~ ^/var/tmp/polarita-zfs-test\.([a-zA-Z0-9]{8})$ && $(realpath -e "$testdir") == "$testdir" ]]
    pool=polarita_test_${testdir##*.}
    disk=$testdir/disk
    base=$testdir/data
    [[ -f $disk && ! -L $disk ]]
else
    [[ $# == 1 && -b $disk && $(lsblk -dno SERIAL "$disk") == incus_data ]]
    sys=/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_incus_root
    [[ -b $sys && $(readlink -f "$disk") != "$(readlink -f "$sys")" ]]
    [[ -f /etc/polarita/zfs/vtpm.cred && $(cat /etc/polarita/zalozeni-vm) == "$owner" ]]
fi
if ! zpool list -H -o name "$pool" >/dev/null 2>&1; then
    # Importuj pouze z určeného zařízení. Po přerušení mezi vytvořením a uložením GUID může být pool exportován.
    paths=(-d "$disk")
    [[ ! -b ${disk}-part1 ]] || paths+=(-d "${disk}-part1")
    guid=$(zpool import "${paths[@]}" |
        awk -v p="$pool" '$1=="pool:" {wanted=($2==p)} wanted && $1=="id:" {print $2}')
    if [[ -n $guid ]]; then
        [[ $guid =~ ^[0-9]+$ ]]
        candidate=$disk
        [[ ! -b ${disk}-part1 ]] || candidate=${disk}-part1
        zpool import -N -o readonly=on -o cachefile=none -d "$candidate" "$guid"
        found_owner=$(zfs get -Ho value cz.polarita:vm "$pool")
        zpool export "$pool"
        [[ $found_owner == "$owner" ]]
        zpool import -N -o cachefile=none -d "$candidate" "$guid"
    else
        signatures=$(wipefs --no-act --noheadings --output TYPE "$disk")
        if [[ -n $signatures ]]; then
            echo 'Datový disk obsahuje existující signaturu.' >&2
            exit 1
        fi
        if [[ -b $disk ]]; then
            [[ $(lsblk -nrpo NAME "$disk" | wc -l) -eq 1 && -z $(lsblk -dno MOUNTPOINTS "$disk") ]]
        fi
        if [[ -b $disk ]]; then bytes=$(blockdev --getsize64 "$disk"); else bytes=$(stat -c %s "$disk"); fi
        [[ $bytes =~ ^[1-9][0-9]*$ ]]
        if ! cmp -s -n "$bytes" "$disk" /dev/zero; then
            echo 'Datové zařízení není prázdné nebo je nelze celé přečíst.' >&2
            exit 1
        fi
        if [[ -e $base ]]; then
            [[ -d $base && ! -L $base && -z $(find "$base" -mindepth 1 -maxdepth 1 -print -quit) ]]
        fi
        zpool create -o ashift=12 -o cachefile=none -m "$base" -O encryption=aes-256-gcm -O keyformat=hex \
            -O "keylocation=file://$key" -O compression=lz4 -O atime=off -O "cz.polarita:vm=$owner" "$pool" "$disk"
    fi
fi
[[ $(zfs get -Ho value cz.polarita:vm "$pool") == "$owner" ]]
[[ $(zfs get -Ho value mountpoint "$pool") == "$base" ]]
[[ $(zfs get -Ho value encryption "$pool") == aes-256-gcm ]]
zpool status -P "$pool" | awk -v d="$disk" '$1==d || $1==d"-part1" {ok=1} END {exit !ok}'
if [[ $(zfs get -Ho value keystatus "$pool") != available ]]; then zfs load-key -L "file://$key" "$pool"; fi
zfs load-key -n -L "file://$key" "$pool" >/dev/null
zfs set keylocation=prompt "$pool"
if [[ $(zfs get -Ho value mounted "$pool") == no ]]; then zfs mount "$pool"; fi
for sub in infra apps data data/{incus,postgres,garage,gitea,pgbackrest,legal-archive,vaultwarden,airgap-spool,airgap-models,clamav-db} vault workspace backups; do
    dataset=$pool/$sub
    if ! zfs list -Ho name "$dataset" >/dev/null 2>&1; then
        options=()
        [[ $sub != data/postgres ]] || options=(-o recordsize=8k)
        zfs create "${options[@]}" "$dataset"
    fi
    [[ $(zfs get -Ho value encryptionroot "$dataset") == "$pool" ]]
    if [[ $(zfs get -Ho value mounted "$dataset") == no ]]; then zfs mount "$dataset"; fi
    [[ $(findmnt -no SOURCE --mountpoint "$base/$sub") == "$dataset" ]]
    chmod 0750 "$base/$sub"
done
install -d -m 0750 "$base"/workspace/{11..18} "$base"/workspace/dukazy/blok-{00..07} \
    "$base"/workspace/{karantena,isds-podatelna,ai-finops/eval-suite}
[[ $(zpool list -Ho health "$pool") == ONLINE && $(zfs get -Ho value recordsize "$pool/data/postgres") == 8K ]]
printf 'Ověřen vyhrazený datový pool %s a šifrované datasety.\n' "$pool"
