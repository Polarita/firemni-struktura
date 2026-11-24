"""Sestaví šifrovanou zálohu dat testovacího ředitelství v účelovém repozitáři."""
from contextlib import closing, contextmanager
import fcntl
import gzip
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.request import Request

from pristup import CA, REPO, credential
import infrastruktura
TEST = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(TEST/"objekty"))
import provoz
sys.path.insert(0,str(TEST/"databaze"))
import obnova as pg
sys.path.insert(0,str(TEST/"pamet"))
from znalosti import DOCS

WORK = Path("/srv/polarita/infra/restic-test")
BACKUPS = Path("/srv/polarita/backups")


def rest_env(repo=REPO):
    return {**os.environ,"RESTIC_REPOSITORY":repo,"RESTIC_REST_USERNAME":"polarita-test",
            "RESTIC_REST_PASSWORD":credential("restic-http"),"RESTIC_PASSWORD":credential("restic-repozitar"),
            "GOMAXPROCS":"2","GOMEMLIMIT":"180MiB"}


def rest(env,*args,check=True,**kwargs):
    return subprocess.run(["restic","--cacert",CA,"--no-cache","-o","rest.connections=2",*args],
                          env=env,check=check,**kwargs)


def ensure_repo(env):
    r=rest(env,"snapshots","--no-lock","--json",check=False,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    if r.returncode==10:
        rest(env,"init","--repository-version","2",stdout=subprocess.DEVNULL)
    elif r.returncode:
        raise RuntimeError("Otevření záložního repozitáře selhalo s kódem "+str(r.returncode))


@contextmanager
def snapshot(dataset):
    if not dataset.startswith("polarita_zfs/"):
        raise ValueError("Chybný dataset sběru")
    base=Path(subprocess.check_output(["zfs","get","-Ho","value","mountpoint",dataset],text=True).strip())
    mark="restic-sber-"+secrets.token_hex(8)
    name=dataset+"@"+mark
    subprocess.run(["zfs","snapshot",name],check=True)
    try:
        yield base/".zfs/snapshot"/mark
    finally:
        subprocess.run(["zfs","destroy",name],check=True)


def copytree(src,dst):
    shutil.copytree(src,dst,symlinks=True)


def hashfile(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def collect(root):
    original = pg.proof(pg.DB,"postgres").hex()
    with subprocess.Popen(["incus","exec","-T",pg.DB,"--","runuser","-u","postgres","--",
                           pg.PG+"pg_dumpall","--no-tablespaces"],stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) as dump:
        with dump.stdout, gzip.open(root/"cluster.sql.gz","wb",compresslevel=3) as out:
            shutil.copyfileobj(dump.stdout,out)
        if dump.wait():
            raise RuntimeError("Export databází selhal")
    if pg.proof(pg.DB,"postgres").hex()!=original:
        raise RuntimeError("Během sběru se změnila struktura databází")
    (root/"postgres.sha256").write_text(original+"\n")
    point = subprocess.run(["incus","exec","-T",pg.DB,"--","bash","-se"],
                           input=(TEST/"zalohy/wal-sber.sh").read_bytes(),stdout=subprocess.PIPE,
                           check=True,timeout=1800).stdout.decode().splitlines()[-1]
    if not re.fullmatch(r"polarita_[0-9a-f]{32} [0-9A-F]+/[0-9A-F]+ [0-9A-F]+/[0-9A-F]+", point):
        raise RuntimeError("Chybí cílový bod obnovy v potvrzeném WAL segmentu")
    (root/"pitr-cil.txt").write_text(point+"\n")
    with snapshot("polarita_zfs/data/postgres") as src:
        subprocess.run(["tar","-cf",str(root/"pgbackrest.tar"),"-C",str(src/"test/pgbackrest"),"."],check=True)
    with snapshot("polarita_zfs/vault") as src:
        target=root/"znalosti"
        target.mkdir()
        for name in (".git",*DOCS):
            copytree(src/name,target/name)
        shutil.copyfile(src/".gitignore",target/".gitignore")
    with snapshot("polarita_zfs/data/vaultwarden") as src:
        copytree(src/"test",root/"vaultwarden")
    with snapshot("polarita_zfs/data/gitea") as src:
        copytree(src/"test/git",root/"gitea")
        for name in ("lfs","attachments","avatars","repo-avatars","packages","repo-archive","actions_log","actions_artifacts"):
            extra=src/"test/data"/name
            if extra.is_dir():
                copytree(extra,root/"gitea-data"/name)
    with snapshot("polarita_zfs/data/legal-archive/test") as src:
        target=root/"legal-archive"
        target.mkdir()
        for area in provoz.hovory.uloz.AREAS:
            copytree(src/area,target/area)
    with provoz.manager() as admin:
        token = provoz.p.login(provoz.p.credentials("reditelstvi-test", admin))
        try:
            value = provoz.p.request("GET", "test/data/reditelstvi", token=token)["data"]["data"]["vzorek"]
            (root/"openbao.sha256").write_text(hashlib.sha256(value.encode()).hexdigest()+"\n")
        finally:
            provoz.p.request("POST", "auth/token/revoke-self", {}, token)
        req=Request(provoz.p.BASE+"sys/storage/raft/snapshot",headers={"X-Vault-Token":admin})
        with provoz.p.HTTP.open(req,timeout=60) as remote,(root/"openbao.snap").open("xb") as out:
            shutil.copyfileobj(remote,out)
        keys={name:provoz.key_for(name,admin) for name in provoz.p.BUCKETS if name!="hovory"}
    for bucket,key in keys.items():
        dst=root/"garage"/bucket
        dst.mkdir(parents=True)
        listing=[]
        with closing(provoz.client(key)) as s3:
            for pages in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
                for obj in pages.get("Contents",[]):
                    name=obj["Key"]
                    filename=hashlib.sha256(name.encode()).hexdigest()
                    reply=s3.get_object(Bucket=bucket,Key=name,IfMatch=obj["ETag"])
                    with closing(reply["Body"]) as stream,(dst/filename).open("xb") as out:
                        shutil.copyfileobj(stream,out,1024*1024)
                    if reply["ETag"]!=obj["ETag"] or (dst/filename).stat().st_size!=reply["ContentLength"]:
                        raise RuntimeError("Garage změnila objekt během sběru")
                    listing.append({"klic":name,"soubor":filename,"metadata":reply["Metadata"],"typ":reply.get("ContentType","application/octet-stream")})
        (dst/"seznam.json").write_text(json.dumps(listing,ensure_ascii=False))
    chat = root / "zulip"
    chat.mkdir()
    with snapshot("polarita_zfs/data/zulip") as source:
        app = source / "aplikace"
        shutil.copyfile(app / "zulip-secrets.conf", chat / "zulip-secrets.conf")
        copytree(app / "uploads", chat / "uploads")
    shutil.copyfile("/srv/polarita/infra/zulip-test/conf/pozice.json", chat / "pozice.json")
    with snapshot("polarita_zfs/data/paperclip") as source:
        target = root / "paperclip"
        target.mkdir()
        shutil.copyfile(source / "pozice.json", target / "pozice.json")
        copytree(source / "test", target / "data")
    infrastruktura.collect(root, snapshot)
    sums={str(f.relative_to(root)):hashfile(f) for f in root.rglob("*") if not f.is_symlink() and f.is_file()}
    (root/"soubory.sha256.json").write_text(json.dumps(sums,sort_keys=True))
    return len(sums)


def backup():
    env=rest_env()
    ensure_repo(env)
    with TemporaryDirectory(dir=BACKUPS) as stage:
        root=Path(stage)
        count=collect(root)
        result=rest(env,"backup","--json","--host","polarita-hq","--tag","firma-test",".",cwd=root,stdout=subprocess.PIPE)
    summary=[json.loads(line) for line in result.stdout.splitlines()]
    snap=next(row["snapshot_id"] for row in summary if row["message_type"]=="summary")
    rest(env,"check","--read-data",stdout=subprocess.DEVNULL)
    temp=WORK/".posledni-otisk"
    temp.write_text(snap+"\n")
    temp.replace(WORK/"posledni-otisk")
    print(f"Restic uložil {count} souborů v šifrovaném snapshotu {snap} a přečetl data při kontrole.",flush=True)
    return snap


if __name__=="__main__":
    if socket.gethostname().split(".")[0]!="polarita-hq" or os.geteuid():
        raise SystemExit("Záloha patří do firemní VM")
    os.umask(0o077)
    with (WORK/".sber").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        backup()
