"""Uloží konfiguraci aktivních služeb a konzistentní exporty jejich datových svazků do obecné zálohy."""
import json
from pathlib import Path
import shutil
import subprocess


def collect(root, snapshot):
    target=root/"infrastruktura"
    target.mkdir()
    with snapshot("polarita_zfs/infra") as source:
        # Cache poskytovatelů a připravená vydání mají původ v Gitu.
        for state in sorted(source.glob("*/terraform.tfstate"))+sorted(source.glob("*/tofu/terraform.tfstate")):
            relative=state.parent.relative_to(source)
            dest=target/"opentofu"/relative
            dest.mkdir(parents=True)
            for item in [state,*state.parent.glob("*.tf"),state.parent/".terraform.lock.hcl"]:
                shutil.copyfile(item,dest/item.name)
        for relative in ("incus/preseed.yaml","hrana/conf/Caddyfile","hrana/headscale/config.yaml",
                         "hrana/headscale/policy.hujson","hrana/headscale/derp.yaml","keycloak-test/conf/start.sh",
                         "mx-test/conf/config.json","mx-test/conf/plan.ndjson","mx-test/conf/start.sh"):
            dest=target/relative
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/relative,dest)
    with (target/"incus/instance.json").open("wb") as out:
        subprocess.run(["incus","list","--format=json"],check=True,stdout=out)
    for resource in ("profile","network","project","storage"):
        records=json.loads(subprocess.check_output(["incus",resource,"list","--format=json"]))
        dest=target/"incus"/(resource+".json")
        dest.write_text(json.dumps(records,ensure_ascii=False,sort_keys=True))
    # Oba exporty zachytí výhradně svůj svazek, včetně WAL příslušné databáze.
    subprocess.run(["systemctl","start","polarita-headscale-zaloha.service"],check=True)
    shutil.copyfile("/srv/polarita/backups/headscale/posledni.tar",target/"headscale.tar")
    subprocess.run(["incus","storage","volume","export","default","stalwart-mx-test-data",
                    str(target/"stalwart-mx.tar"),"--volume-only","--compression","none"],check=True,stdout=subprocess.DEVNULL)
    if Path("/srv/polarita/data/checkmk/test/polarita/etc").is_dir():
        with snapshot("polarita_zfs/data/checkmk") as source:
            # Reprodukovatelný binární balík leží mimo lokalitu. Zde jsou pravidla a místní rozšíření.
            for name in ("etc","local"):
                shutil.copytree(source/"test/polarita"/name,target/"checkmk"/name,symlinks=True)
