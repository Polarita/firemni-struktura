"""Obnova běžné nahrávky a přepisu, výmaz provozní kopie a expirace jediné testovací skupiny."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
import secrets
import socket
import subprocess
import wave

from hovory_sber import collect
from sber import REPO, provoz, rest, rest_env


def main():
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Zkouška patří do firemní VM")
    now = datetime.now(timezone.utc)
    captured = now-timedelta(days=84)
    run = secrets.token_hex(12)
    prefix = "zkouska-hovory-"+run+"-"
    path = "zkouska/"+run+"/"
    buf = io.BytesIO()
    with wave.open(buf,"wb") as wav:
        wav.setparams((2,2,8000,0,"NONE","not compressed"))
        wav.writeframes(b"\x05\x00\x0a\x00"*800)
    files = {path+"zvuk.wav":buf.getvalue(),path+"prepis.txt":("Test oddělené zálohy "+run).encode()}
    with provoz.manager() as manager:
        creds = provoz.key_for("hovory",manager)
    with closing(provoz.client(creds)) as s3:
        try:
            for key,value in files.items():
                s3.put_object(Bucket="hovory",Key=key,Body=value,Metadata={"porizeno":captured.isoformat(),"legal-hold":"false"})
            # Zrychlené hodiny se použijí pouze pro nově vytvořené syntetické klíče a repozitář.
            name = prefix+captured.date().isoformat()
            snaps = collect(s3,now-timedelta(days=2),prefix,set(files))
            env = rest_env(REPO.replace("/firma/","/"+name+"/"))
            snap = snaps[name]
            manifest = json.loads(rest(env,"dump",snap,"/seznam.json",capture_output=True).stdout)
            if set(manifest) != set(files):
                raise RuntimeError("Repozitář zkušebního dne má jiný obsah")
            for key,value in files.items():
                if rest(env,"dump",snap,"/"+manifest[key]["soubor"],capture_output=True).stdout != value:
                    raise RuntimeError("Obnovená provozní nahrávka nebo přepis se liší")
            # Provozní retence běží se skutečným časem, stejně jako běžný časovač.
            provoz.expire(s3,now)
            for key in files:
                provoz.rejected(s3.head_object,404,Bucket="hovory",Key=key)
            cmd = ["incus","exec","-T","restic-test","--","runuser","-u","pol-restic","--",
                   "python3","/usr/local/lib/polarita-restic/hovory_retence.py","--zkouska",run]
            subprocess.run(cmd+[(captured+timedelta(days=89)).date().isoformat()],check=True)
            rest(env,"check","--read-data",capture_output=True)
            subprocess.run(cmd+[(captured+timedelta(days=90)).date().isoformat()],check=True)
            target = "/var/lib/restic-test/data/polarita-test/"
            subprocess.run(["incus","exec","-T","restic-test","--","test","!","-e",target+name],check=True)
            if rest(env,"cat","config",check=False,capture_output=True).returncode!=10:
                raise RuntimeError("Expirovaný denní repozitář zůstává přístupný")
            general_env = rest_env()
            snapshots = json.loads(rest(general_env,"snapshots","--no-lock","--json",capture_output=True).stdout)
            if not snapshots:
                raise RuntimeError("Chybí obecná záloha pro kontrolu oddělení")
            fingerprints = {hashlib.sha256(key.encode()).hexdigest() for key in files}
            for row in snapshots:
                members = rest(general_env,"ls","--json",row["id"],capture_output=True).stdout
                for line in members.splitlines():
                    name = json.loads(line).get("path","")
                    if name.startswith("/garage/hovory/") or run in name or any(digest in name for digest in fingerprints):
                        raise RuntimeError("Obecný repozitář obsahuje provozní hovor")
            print(f"Oddělený repozitář obnovil oba původní soubory. V 84. dni byly pryč z Garage, do konce 90denní lhůty zmizel celý denní repozitář. Zkontrolováno obecných snapshotů: {len(snapshots)}.")
        finally:
            for key in files:
                s3.delete_object(Bucket="hovory",Key=key)


if __name__ == "__main__":
    main()
