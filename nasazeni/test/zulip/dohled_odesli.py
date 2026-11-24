"""Přijme stav Checkmk na privátním Unix socketu a zavolá nativní webhook Zulipu."""
from datetime import datetime, timezone
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlencode


def send(event):
    host, service, status, kind = (event[k] for k in ("uzel","sluzba","stav","druh"))
    if host != "polarita-hq" or (status,kind) not in (
        ("CRITICAL","PROBLEM"), ("DOWN","PROBLEM"), ("OK","RECOVERY"), ("UP","RECOVERY")
    ):
        raise ValueError("Neznámý typ události")
    if not isinstance(service,str) or not re.fullmatch(r"[\w .:/()\-]{1,128}",service):
        raise ValueError("Neplatný název služby")
    credentials = Path(os.environ["CREDENTIALS_DIRECTORY"])
    key = json.loads((credentials/"zulip-webhook").read_bytes())
    message = f"Checkmk TEST · {host} · {service} · {status} ({kind})"
    fields = {"api_key":key, "stream":"17-it-secops", "topic":f"POL-{datetime.now(timezone.utc).year}-00000",
              "payload":json.dumps({"text":message},ensure_ascii=False)}
    conn = HTTPConnection("127.0.0.1",18184,timeout=12)
    try:
        conn.request("POST","/api/v1/external/slack_incoming",urlencode(fields),headers={
            "Content-Type":"application/x-www-form-urlencoded","Host":os.environ["POLARITA_WEB"]+":8444"})
        reply = conn.getresponse()
        if reply.status != 200:
            raise RuntimeError(f"Zulip vrátil HTTP {reply.status}")
        data = json.loads(reply.read(4096))
        if data.get("result") != "success" or data.get("ok") is not True:
            raise RuntimeError("Zulip nepotvrdil webhook")
    finally:
        conn.close()


if __name__ == "__main__":
    line = sys.stdin.buffer.readline(2049)
    if not line.endswith(b"\n") or len(line)>2048:
        raise SystemExit("Neplatná délka oznámení")
    send(json.loads(line))
    print("OK",flush=True)
