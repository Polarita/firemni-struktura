"""Uživatelé v jednotlivých odděleních dostanou odezvu svých botů přes nativní Zulip API."""
import base64
import json
from datetime import datetime, timezone
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from zerver.actions.message_send import internal_send_stream_message
from zerver.models import Message, Realm, Stream, UserProfile


def call(bot, method, path, fields=None, *, expected=200):
    conn = HTTPConnection("127.0.0.1",80,timeout=15)
    try:
        auth = base64.b64encode((bot.delivery_email+":"+bot.api_key).encode()).decode()
        headers = {"Host":settings.EXTERNAL_HOST,"X-Forwarded-Proto":"https","Authorization":"Basic "+auth,
                   "Content-Type":"application/x-www-form-urlencoded"}
        conn.request(method,path,body=urlencode(fields) if fields else None,headers=headers)
        reply = conn.getresponse()
        payload = json.loads(reply.read(65536))
        if reply.status not in ((expected,) if isinstance(expected,int) else expected):
            raise RuntimeError(f"Zulip odmítl zkoušku účtu {bot.delivery_email} (HTTP {reply.status})")
        return payload
    finally:
        conn.close()


realm = Realm.objects.get(string_id=Realm.SUBDOMAIN_FOR_ROOT_DOMAIN,name="Ředitelství Polarity")
owner = UserProfile.objects.get(realm=realm,delivery_email="spravce@polarita.test",role=100,is_active=True)
names = json.loads(Path("/etc/polarita-zulip/pozice.json").read_bytes())
if len(names)!=20:
    raise RuntimeError("Nesouhlasí počet účtů v kanonu")
topic = f"POL-{datetime.now(timezone.utc).year}-00001"
samples = {}
for number in sorted({code[:2] for code in names}):
    channel = Stream.objects.get(realm=realm,name__startswith=number+"-",invite_only=True,deactivated=False)
    content = "Ověření příjmu a odpovědi pracovních botů oddělení "+number+" v TEST."
    messages = Message.objects.filter(sender=owner,recipient_id=channel.recipient_id,subject=topic,content=content)
    if not messages.exists():
        internal_send_stream_message(owner,channel,topic,content,acting_user=owner)
    samples[number] = (channel,messages.get())

for code in sorted(names):
    channel, sample = samples[code[:2]]
    bot = UserProfile.objects.get(realm=realm,delivery_email=f"ai-{code}-bot@polarita.test",bot_owner=owner,
                                  is_active=True,bot_type=UserProfile.DEFAULT_BOT)
    received = call(bot,"GET",f"/api/v1/messages/{sample.id}?apply_markdown=false")
    if received.get("result")!="success" or received["message"]["content"]!=sample.content:
        raise RuntimeError("Bot nepřečetl zadání ze svého oddělení")
    other = next(row for number,row in samples.items() if number!=code[:2])[1]
    denied = call(bot,"GET",f"/api/v1/messages/{other.id}",expected=(400,403,404))
    if denied.get("result")!="error" or "message" in denied:
        raise RuntimeError("Bot přečetl cizí soukromý kanál")
    ack = f"{code} · TEST · Přijata kontrolní zpráva {sample.id}."
    arrivals = Message.objects.filter(sender=bot,recipient_id=channel.recipient_id,subject=topic,content=ack)
    if not arrivals.exists():
        written = call(bot,"POST","/api/v1/messages",{"type":"stream","to":channel.id,"topic":topic,"content":ack})
        if written.get("result")!="success" or not arrivals.filter(id=written["id"]).exists():
            raise RuntimeError("Zulip nepotvrdil odpověď odeslanou nativním botem")
    print(f"{code} · {channel.name} · zadání {sample.id}, odpověď {arrivals.get().id}",flush=True)
print("Všech 20 pracovních botů přečetlo kontrolní zprávu a odpovědělo ve vlastním tématu. Přístup do cizího soukromého kanálu Zulip odmítl.")
