"""Přečte topologii ředitelství a ověří, že nasazení pokračuje ve správné VM a na správném disku."""
from datetime import datetime, timezone
import json
import socket
import subprocess
import sys


def over():
    if socket.gethostname().split(".")[0] != "ejpovice":
        raise SystemExit("Inventuru spusť na Ejpovicích")
    incus = ["sudo", "-n", "incus"]
    def query(path):
        return json.loads(subprocess.check_output(incus + ["query", path + "?project=polarita"]))

    vm = query("/1.0/instances/polarita-hq")
    if (vm["name"], vm["type"], vm["location"], vm["status"]) != (
        "polarita-hq", "virtual-machine", "ejpovice", "Running"
    ):
        raise ValueError("Projekt polarita nepotvrdil běžící firemní VM na Ejpovicích")
    devices = vm["expanded_devices"]
    system, data = devices["root"], devices["data"]
    if ((system["type"], system["pool"], system["path"]) != ("disk", "zrcadlo", "/")
            or (data["type"], data["pool"], data["source"]) != ("disk", "zrcadlo", "polarita-hq-data")
            or not any(device["type"] == "tpm" for device in devices.values())):
        raise ValueError("Nesouhlasí systémový disk, vyhrazený datový disk nebo vTPM")
    volume = query("/1.0/storage-pools/zrcadlo/volumes/custom/polarita-hq-data")
    if volume["content_type"] != "block" or volume["used_by"] != ["/1.0/instances/polarita-hq?project=polarita"]:
        raise ValueError("Datový svazek nepatří výlučně firemní VM")
    guest = incus + ["exec", "-T", "--project", "polarita", "polarita-hq", "--"]
    measured = subprocess.check_output(guest + ["bash", "-se"], text=True, input="""
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
[[ -c /dev/tpmrm0 && -c /dev/kvm && -d /sys/firmware/efi ]]
systemctl is-active --quiet polarita-zfs.service
systemctl is-active --quiet chrony.service
systemctl is-active --quiet auditd.service
[[ $(findmnt -n -o SOURCE --mountpoint /srv/polarita) == polarita_zfs ]]
[[ $(zpool list -Ho health polarita_zfs) == ONLINE ]]
[[ $(zfs get -Ho value encryption polarita_zfs) == aes-256-gcm ]]
[[ $(zfs get -Ho value keystatus polarita_zfs) == available ]]
disk=/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_incus_data
[[ -b $disk && -b ${disk}-part1 && -b /dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_incus_root ]]
zpool status -P polarita_zfs | grep -Fq "${disk}-part1"
systemd-run --quiet --wait --pipe --collect \\
    -p LoadCredentialEncrypted=polarita-zfs.key:/etc/polarita/zfs/vtpm.cred \\
    sh -ec 'zfs load-key -n -L "file://${CREDENTIALS_DIRECTORY}/polarita-zfs.key" polarita_zfs' >/dev/null
. /etc/os-release
printf '%s\\n' "$PRETTY_NAME"
""").strip()
    config = vm["expanded_config"]
    return {
        "cas_utc": datetime.now(timezone.utc).isoformat(), "projekt": "polarita", "vm": vm["name"],
        "uzel": vm["location"], "os": measured, "cpu": config["limits.cpu"], "ram": config["limits.memory"],
        "pool_incus": system["pool"], "systemovy_disk": system["size"], "datovy_disk": volume["config"]["size"],
        "zfs": "polarita_zfs ONLINE, aes-256-gcm", "vtpm_overilo_klic": True, "kvm": True,
        "sluzby": ["auditd", "chrony", "polarita-zfs"],
    }


if __name__ == "__main__":
    json.dump(over(), sys.stdout, indent=2, ensure_ascii=False)
    print()
