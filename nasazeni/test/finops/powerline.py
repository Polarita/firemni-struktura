"""Připnuté vydání stavového řádku a licence. Spouští se pouze v úloze TEST."""
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import socket
import subprocess
import tarfile
from urllib.request import urlopen

SOURCE = Path(__file__).resolve().parent
ASSET = "https://github.com/david-strejc/claude-powerline-rust/releases/download/v1.2.0/claude-powerline-linux-x64.tar.gz"
LICENSE = "https://raw.githubusercontent.com/david-strejc/claude-powerline-rust/v1.2.0/LICENSE"

def cached(folder, filename, url, digest):
    file=folder/filename
    if not file.exists() or sha256(file.read_bytes()).hexdigest()!=digest:
        with urlopen(url, timeout=35) as response:
            data=response.read(2*1024*1024+1)
        if len(data)>2*1024*1024 or sha256(data).hexdigest()!=digest:
            raise RuntimeError("Nesouhlasí původ souboru "+filename)
        pending=file.with_suffix(".next")
        pending.write_bytes(data)
        os.replace(pending,file)
    return file

def main():
    if os.geteuid() or socket.gethostname().split(".")[0]!="polarita-hq":
        raise SystemExit("Panel patří do firemní VM")
    work=Path("/var/cache/polarita-finops-powerline/1.2.0")
    work.mkdir(mode=0o700,parents=True,exist_ok=True)
    bundle=cached(work,"powerline.tar.gz",ASSET,"52380c22020cbad502f15f0ff5b05bd0da1b38261f37edacf7637d227459cf55")
    license_file=cached(work,"LICENSE",LICENSE,"c4d1d6f8765a9f2206cc5daa22321bc5668daac6680e6ef65dec5707e5258c00")
    with tarfile.open(fileobj=BytesIO(bundle.read_bytes())) as archive:
        member,=archive.getmembers()
        if member.name!="claude-powerline" or not member.isfile() or member.size!=2299008:
            raise RuntimeError("Neznámý formát vydání")
        (work/"claude-powerline").write_bytes(archive.extractfile(member).read())
    target="/usr/local/lib/polarita/finops"
    inside=["incus","exec","-T","postgres-test","--"]
    subprocess.run(inside+["install","-d","-m0755",target],check=True)
    for file, name, mode in [(work/"claude-powerline",target+"/claude-powerline","0755"),
                              (license_file,target+"/LICENSE","0644"),(SOURCE/"powerline.json",target+"/powerline.json","0644"),
                              (SOURCE/"panel.py","/usr/local/bin/polarita-powerline","0755")]:
        subprocess.run(["incus","file","push","--mode",mode,file,"postgres-test"+name+".next"],check=True)
        subprocess.run(inside+["mv","-f",name+".next",name],check=True)
    line=subprocess.check_output(inside+["runuser","-u","pol_finops_read","--","/usr/local/bin/polarita-powerline"],text=True)
    if "470,00 USD" not in line or "70,50 USD" not in line:
        raise RuntimeError("Panel nepotvrdil měsíční limit a rezervu")
    print("Stavový řádek claude-powerline-rust 1.2.0 přečetl živé kvóty přes místní účet pouze pro čtení.")

if __name__=="__main__":
    main()
