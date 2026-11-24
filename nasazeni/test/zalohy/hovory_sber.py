"""Oddělené zálohy provozního zvuku a přepisů podle dne pořízení UTC."""
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
from tempfile import TemporaryDirectory

from sber import BACKUPS, REPO, ensure_repo, provoz, rest, rest_env


def collect(s3, now, prefix="hovory-", only_keys=None):
    if prefix != "hovory-" and not re.fullmatch(r"zkouska-hovory-[a-f0-9]{24}-",prefix):
        raise ValueError("Neplatná skupina denních záloh")
    if prefix != "hovory-" and not only_keys:
        raise ValueError("Zkušební cíl potřebuje explicitní seznam vzorků")
    days = defaultdict(list)
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket="hovory"):
        for entry in page.get("Contents",[]):
            key = entry["Key"]
            if only_keys is not None and key not in only_keys:
                continue
            head = s3.head_object(Bucket="hovory",Key=key)
            meta = {k.lower():v for k,v in head["Metadata"].items()}
            flag = meta.get("legal-hold","false").lower()
            if flag == "true":
                continue
            if flag != "false" or key.startswith("legal-hold/"):
                raise ValueError("Rozpor v ochraně hovoru")
            captured = datetime.fromisoformat(meta["porizeno"])
            if captured.tzinfo is None or captured > now:
                raise ValueError("Neplatný okamžik pořízení hovoru")
            if now < captured + timedelta(days=83):
                day = captured.astimezone(timezone.utc).date()
                days[day].append((key,head["ETag"],head.get("ContentType","application/octet-stream"),meta))
    snapshots = {}
    for day, items in sorted(days.items()):
        name = prefix+day.isoformat()
        with TemporaryDirectory(dir=BACKUPS) as tmp:
            folder = Path(tmp)
            manifest = {}
            for key, etag, content_type, meta in items:
                filename = hashlib.sha256(key.encode()).hexdigest()
                obj = s3.get_object(Bucket="hovory", Key=key, IfMatch=etag)
                with closing(obj["Body"]) as stream, (folder/filename).open("xb") as out:
                    shutil.copyfileobj(stream,out,1024*1024)
                if (folder/filename).stat().st_size != obj["ContentLength"]:
                    raise RuntimeError("Předčasný konec přenosu hovoru")
                manifest[key] = {"soubor":filename,"metadata":meta,"typ":content_type}
            (folder/"seznam.json").write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True))
            env = rest_env(REPO.replace("/firma/","/"+name+"/"))
            ensure_repo(env)
            result = rest(env,"backup","--host","polarita-hq","--tag",name,"--json",".",cwd=folder,capture_output=True)
            snapshots[name] = next(item["snapshot_id"] for item in map(json.loads,result.stdout.splitlines())
                                   if item["message_type"]=="summary")
    return snapshots


def main():
    if os.geteuid() or socket.gethostname().split(".")[0]!="polarita-hq":
        raise SystemExit("Sběr hovorů patří do firemní VM")
    os.umask(0o077)
    with Path("/run/polarita-hovory-retence.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with provoz.manager() as manager:
            creds = provoz.key_for("hovory",manager)
        with closing(provoz.client(creds)) as s3:
            snapshots = collect(s3,datetime.now(timezone.utc))
    print(f"Počet denních repozitářů obsahujících běžné hovory z tohoto sběru: {len(snapshots)}.")


if __name__ == "__main__":
    main()
