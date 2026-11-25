"""Přístup aplikací do Garage přes TLS a SigV4. Do protokolu se vypisují pouze výsledky."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone, timedelta
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import sys
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "trezor"))
import pristupy as p

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archiv"))
import hovory

INSIDE = ["incus", "exec", "-T", "garage-test", "--"]
CERT = Path("/srv/polarita/infra/garage-test/verejny-certifikat.pem")


def client(key):
    return boto3.client("s3", region_name="polarita-test", endpoint_url="https://10.239.33.14:8443",
                        aws_access_key_id=key["id"], aws_secret_access_key=key["tajemstvi"], verify=str(CERT),
                        config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=15,
                                      retries={"max_attempts": 2}, s3={"addressing_style": "path"},
                                      request_checksum_calculation="when_required",
                                      response_checksum_validation="when_required"))


@contextmanager
def manager():
    p.HTTP = p.build_opener(p.ProxyHandler({}), p.HTTPSHandler(context=ssl.create_default_context(cafile=str(p.WORK / "ca.crt"))))
    token = p.login(p.recover("bao-sprava"))
    try:
        yield token
    finally:
        p.request("POST", "auth/token/revoke-self", {}, token)


def key_for(bucket, admin):
    token = p.login(p.credentials("s3-" + bucket, admin))
    try:
        other = next(x for x in p.BUCKETS if x != bucket)
        p.expect_forbidden("GET", "test/data/objekty/" + other, token)
        p.expect_forbidden("GET", "test/data/pki/garage-test", token)
        return p.request("GET", "test/data/objekty/" + bucket, token=token)["data"]["data"]
    finally:
        p.request("POST", "auth/token/revoke-self", {}, token)


def expire(s3, now):
    with Path("/run/polarita-hovory-retence.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        process_calls(s3, now)


def process_calls(s3, now):
    removed = 0
    pending = 0
    archived = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket="hovory"):
        for item in page.get("Contents", []):
            key = item["Key"]
            try:
                headers = s3.head_object(Bucket="hovory", Key=key)["Metadata"]
                meta = {name.lower(): value for name, value in headers.items()}
            except ClientError as error:
                if error.response["ResponseMetadata"]["HTTPStatusCode"] == 404:
                    continue
                raise
            hold = meta.get("legal-hold", "").lower()
            if hold not in ("","false","true") or (key.startswith("legal-hold/") and hold!="true"):
                pending += 1
                continue
            if hold == "true":
                try:
                    if hovory.transfer(s3, key, meta):
                        archived += 1
                    else:
                        pending += 1
                except (KeyError, ValueError):
                    pending += 1
                continue
            try:
                captured = datetime.fromisoformat(meta["porizeno"])
                if captured.tzinfo is None or captured > now:
                    raise ValueError("Chybný čas pořízení")
            except (KeyError, ValueError):
                pending += 1
                continue
            if now >= captured + timedelta(days=83):
                s3.delete_object(Bucket="hovory", Key=key)
                removed += 1
    print("Počet objektů po uplynutí 83 dnů od pořízení odstraněných z Garage:", removed, flush=True)
    if archived:
        print("Počet převzatých spisových hovorů s ověřeným snímkem:", archived, flush=True)
    if pending:
        raise RuntimeError(f"Počet záznamů k vyřízení ochrany nebo času pořízení: {pending}")


def rejected(fn, expected, **kwargs):
    try:
        fn(**kwargs)
    except ClientError as error:
        if error.response["ResponseMetadata"]["HTTPStatusCode"] == expected:
            return
        raise
    raise RuntimeError("S3 povolilo neočekávaný přístup")


def verify(keys):
    run = secrets.token_hex(12)
    now = datetime.now(timezone.utc)
    for bucket, creds in keys.items():
        with closing(client(creds)) as s3:
            data = ("Polarita TEST " + run).encode()
            other = next(x for x in keys if x != bucket)
            name = "zkouska/" + run + ".txt"
            s3.put_object(Bucket=bucket, Key=name, Body=data, Metadata={"porizeno": now.isoformat()})
            try:
                obj = s3.get_object(Bucket=bucket, Key=name)
                with obj["Body"] as body:
                    if body.read() != data:
                        raise RuntimeError("Kontrolní čtení vrátilo jiný objekt")
                rejected(s3.list_objects_v2, 403, Bucket=other, MaxKeys=1)
            finally:
                s3.delete_object(Bucket=bucket, Key=name)
    with closing(client(keys["hovory"])) as s3:
        for suffix in ("audio", "prepis"):
            name = "zkouska/" + run + "-" + suffix
            s3.put_object(Bucket="hovory", Key=name, Body=b"TEST",
                          Metadata={"porizeno": (now - timedelta(days=84)).isoformat()})
        expire(s3, now)
        for suffix in ("audio", "prepis"):
            rejected(s3.head_object, 404, Bucket="hovory", Key="zkouska/" + run + "-" + suffix)
    print("Osm účtů zapsalo a přečetlo vlastní vzorek přes HTTPS a SigV4. Přístup do cizího koše byl zamítnut.")
    print("Zkušební nahrávka a přepis z 84. dne prošly stejnou úlohou výmazu jako běžné hovory.")


def uloz_testovaci_hovor(s3, wav, otisk):
    with wav.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != otisk:
            raise ValueError("Otisk stereo nahrávky před uložením nesouhlasí.")
        source.seek(0)
        key = f"zkouska/asterisk/{otisk}.wav"
        obj = {"Bucket": "hovory", "Key": key}
        try:
            s3.head_object(**obj)
        except ClientError as error:
            if error.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
                raise
            s3.put_object(**obj, Body=source, ContentType="audio/wav",
                          Metadata={"porizeno": datetime.now(timezone.utc).isoformat(), "sha256": otisk})
    ulozeno = s3.get_object(**obj)
    with ulozeno["Body"] as body:
        digest = hashlib.sha256()
        for cast in iter(lambda: body.read(65536), b""):
            digest.update(cast)
    if digest.hexdigest() != otisk:
        raise ValueError("Obsah nahrávky v Garage má jiný otisk.")
    metadata = {name.lower(): value for name, value in ulozeno["Metadata"].items()}
    if metadata.get("sha256") != otisk:
        raise ValueError("V metadatech nahrávky Garage chybí správný otisk.")
    print(f"Garage ověřena zpětným čtením přes HTTPS: s3://hovory/{key}")


def main():
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq":
        raise SystemExit("Správa objektů patří do polarita-hq")
    if sys.argv[1:2] == ["--testovaci-hovor"]:
        parser = argparse.ArgumentParser(description="Uložení nahrávky interních klapek TEST")
        parser.add_argument("wav", type=Path)
        parser.add_argument("sha256")
        args = parser.parse_args(sys.argv[2:])
        with manager() as admin:
            key = key_for("hovory", admin)
        with closing(client(key)) as s3:
            uloz_testovaci_hovor(s3, args.wav, args.sha256)
        return
    if sys.argv[1:2] == ["--spisovy-hovor"]:
        parser = argparse.ArgumentParser(description="Předání stereo WAV a přepisu do testovacího spisu")
        parser.add_argument("--spis",required=True)
        parser.add_argument("--roky",required=True,type=int,choices=range(3,11))
        parser.add_argument("--porizeno",required=True)
        parser.add_argument("--wav",required=True,type=Path)
        parser.add_argument("--prepis",required=True,type=Path)
        args = parser.parse_args(sys.argv[2:])
        with manager() as admin:
            key = key_for("hovory",admin)
        with closing(client(key)) as s3:
            receipt = hovory.handover(s3,args.spis,args.roky,args.porizeno,args.wav,args.prepis)
        print("Předávací záznam TEST",receipt)
        return
    if sys.argv[1:] == ["--expirace"]:
        with manager() as admin:
            key = key_for("hovory", admin)
        with closing(client(key)) as s3:
            expire(s3, datetime.now(timezone.utc))
        return
    if sys.argv[1:]:
        raise SystemExit("Neznámá volba správy košů")
    crt = subprocess.check_output([*INSIDE, "cat", "/run/secrets/garage-cert"])
    temp = CERT.with_suffix(".tmp")
    temp.write_bytes(crt)
    temp.replace(CERT)
    subprocess.run([*INSIDE, "systemctl", "enable", "--now", "garage-test.service", "garage-tls.service"], check=True)
    with manager() as admin:
        keys = {bucket: key_for(bucket, admin) for bucket in p.BUCKETS}
    for _ in range(45):
        ready = subprocess.run([*INSIDE, "python3", "-c",
            "import socket; socket.create_connection(('127.0.0.1',3903),1).close()"], stderr=subprocess.DEVNULL)
        if ready.returncode == 0:
            break
        time.sleep(1)
    subprocess.run(["incus","exec","-T","garage-test","--user","17306","--group","17306","--",
                    "python3","/etc/polarita-garage/kose.py"], input=json.dumps(keys).encode(), check=True)
    verify(keys)


if __name__ == "__main__":
    main()
