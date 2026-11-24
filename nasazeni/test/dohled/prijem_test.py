"""Pouze místní příjem testovacích notifikací. Oba protokoly potvrzují až zápis události."""
from datetime import datetime,timezone
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import os
from pathlib import Path
import threading
from aiosmtpd.controller import Controller

FILE=Path("/var/lib/polarita-alert-test/udalosti.jsonl")
LOCK=threading.Lock()


def save(channel,event):
    if not isinstance(event,dict) or set(event)!={"uzel","sluzba","stav","druh"}:
        raise ValueError("Neplatná testovací událost")
    if event["uzel"]!="polarita-hq" or event["stav"] not in ("CRITICAL","DOWN","OK","UP"):
        raise ValueError("Neplatný cíl nebo stav události")
    if not all(isinstance(v,str) and 0<len(v)<=180 for v in event.values()):
        raise ValueError("Neplatné textové pole")
    record={**event,"kanal":channel,"utc":datetime.now(timezone.utc).isoformat()}
    with LOCK,FILE.open("a") as log:
        log.write(json.dumps(record,ensure_ascii=False)+"\n")
        log.flush()
        os.fsync(log.fileno())


class Mail:
    async def handle_DATA(self,server,session,envelope):
        if envelope.rcpt_tos!=["dispecink@polarita.test"]:
            return "550 Neplatny cil TEST"
        try:
            msg=BytesParser(policy=policy.default).parsebytes(envelope.content)
            save("smtp",json.loads(msg.get_content()))
        except (ValueError,TypeError):
            return "550 Neplatny poplach TEST"
        return "250 OK"


class Pager(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_POST(self):
        if self.path!="/botTEST/sendMessage":
            self.send_error(404)
            return
        try:
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=16384:
                raise ValueError()
            msg=json.loads(self.rfile.read(size))
            if msg["chat_id"]!="polarita-test":
                raise ValueError()
            save("telegram-test",json.loads(msg["text"]))
        except (KeyError,ValueError,TypeError):
            self.send_error(400)
            return
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true,"result":{"message_id":1}}')


if __name__=="__main__":
    smtp=Controller(Mail(),hostname="127.0.0.1",port=18025,data_size_limit=16384)
    smtp.start()
    try:
        HTTPServer(("127.0.0.1",18420),Pager).serve_forever()
    finally:
        smtp.stop()
