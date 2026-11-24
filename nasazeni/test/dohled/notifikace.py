#!/usr/bin/python3
# Polarita TEST – doručení kritického stavu a zotavení místnímu protějšku.
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import sys
from urllib.request import ProxyHandler,Request,build_opener

kind=os.environ.get("NOTIFY_NOTIFICATIONTYPE","")
if kind not in ("PROBLEM","RECOVERY"):
    sys.exit(0)
host=os.environ["NOTIFY_HOSTNAME"]
service=os.environ.get("NOTIFY_SERVICEDESC","Hostitel")
status=os.environ["NOTIFY_SERVICESTATE"] if os.environ.get("NOTIFY_WHAT")=="SERVICE" else os.environ["NOTIFY_HOSTSTATE"]
if host!="polarita-hq" or status not in ("CRITICAL","DOWN","OK","UP"):
    sys.exit(0)
event=json.dumps({"uzel":host,"sluzba":service,"stav":status,"druh":kind},ensure_ascii=False)
plugin=Path(sys.argv[0]).name
if plugin=="polarita_smtp":
    msg=EmailMessage()
    msg["From"]="checkmk@polarita.test"
    msg["To"]="dispecink@polarita.test"
    msg["Subject"]="Checkmk TEST "+status
    msg.set_content(event)
    with smtplib.SMTP("127.0.0.1",18025,timeout=5) as smtp:
        smtp.send_message(msg)
elif plugin=="polarita_telegram":
    data=json.dumps({"chat_id":"polarita-test","text":event}).encode()
    request=Request("http://127.0.0.1:18420/botTEST/sendMessage",data=data,headers={"Content-Type":"application/json"})
    with build_opener(ProxyHandler({})).open(request,timeout=5) as reply:
        if not json.load(reply).get("ok"):
            raise RuntimeError("Testovací pager nepotvrdil příjem")
else:
    raise SystemExit("Neznámý místní kanál")
