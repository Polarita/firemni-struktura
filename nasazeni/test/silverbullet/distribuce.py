"""Instaluje konkrétní ověřené upstream binární distribuce pro soukromé služby."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from zipfile import ZipFile

SB = "https://github.com/silverbulletmd/silverbullet/releases/download/3.0.0/silverbullet-server-linux-x86_64.zip"
PROXY = "https://github.com/oauth2-proxy/oauth2-proxy/releases/download/v7.15.6/oauth2-proxy-v7.15.6.linux-amd64.tar.gz"
CACHE = Path("/var/cache/polarita-silverbullet-test")
OUT = Path("/srv/polarita/infra/silverbullet-test/bin")

def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def source(url, checksum):
    target=CACHE/url.rsplit("/",1)[1]
    if not target.is_file() or digest(target)!=checksum:
        pending=target.with_suffix(".part")
        subprocess.run(["curl","-fLsS","--proto","=https","--retry","3","--max-time","180",url,"-o",pending],check=True)
        if digest(pending)!=checksum:
            raise ValueError("Nesouhlasí kontrolní součet distribuce")
        pending.replace(target)
    return target

def install(stream,name):
    with tempfile.NamedTemporaryFile(dir=OUT,delete=False) as f:
        pending=Path(f.name)
        shutil.copyfileobj(stream,f)
        f.flush()
        os.fsync(f.fileno())
        os.fchmod(f.fileno(),0o755)
    target=OUT/name
    if target.exists() and digest(target)==digest(pending):
        pending.unlink()
    else:
        pending.replace(target)

def main():
    if os.geteuid()!=0 or os.uname().nodename.split(".")[0]!="polarita-hq":
        raise SystemExit("Distribuce patří do polarita-hq")
    CACHE.mkdir(mode=0o700,parents=True,exist_ok=True)
    OUT.mkdir(mode=0o755,parents=True,exist_ok=True)
    with ZipFile(source(SB,"8fd5f051a735be9bef2705fe5d4a743b654f0e9b4c970843f0798508d0e9510e")) as z:
        with z.open("silverbullet") as stream:
            install(stream,"silverbullet")
    with tarfile.open(source(PROXY,"91b3e86d9c2de679a516e6696704e3fd1acf67e8b8f7be77b618f086f72fb1f0")) as archive:
        with archive.extractfile("oauth2-proxy-v7.15.6.linux-amd64/oauth2-proxy") as stream:
            install(stream,"oauth2-proxy")

if __name__=="__main__":
    main()
