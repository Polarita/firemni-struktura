"""Spouští se v Django shellu Zulipu. Vytváří jen účty a kanály této testovací organizace."""
import json
from pathlib import Path
from zerver.actions.message_send import internal_send_stream_message
from zerver.lib.upload import upload_message_attachment
from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import do_create_user
from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.streams import create_stream_if_needed
from zerver.models import Attachment, Realm, Recipient, Subscription, UserProfile

names = {"11":"11-vedeni","12":"12-marketing","13":"13-eshop-a-nakup","14":"14-elektro-a-zakazky",
         "15":"15-pravo-a-normy","16":"16-finance-a-kancelar","17":"17-it-secops","18":"18-hr-a-teren"}
employees = json.loads(Path("/etc/polarita-zulip/pozice.json").read_bytes())
if len(employees)!=20 or {code[:2] for code in employees}!=set(names):
    raise ValueError("Soupis pozic nesouhlasí s firemní strukturou")

realm = Realm.objects.filter(string_id=Realm.SUBDOMAIN_FOR_ROOT_DOMAIN).first()
if realm is None:
    realm = do_create_realm(string_id=Realm.SUBDOMAIN_FOR_ROOT_DOMAIN,name="Ředitelství Polarity",
                            invite_required=True,enable_spectator_access=False,default_language="cs")
if realm.name!="Ředitelství Polarity" or not realm.invite_required or realm.enable_spectator_access:
    raise ValueError("Kořenová organizace Zulipu má jinou konfiguraci")
account = "spravce@polarita.test"
owner = UserProfile.objects.filter(realm=realm,delivery_email__iexact=account).first()
if owner is None:
    owner = do_create_user(account,None,realm,"Správce TEST",role=UserProfile.ROLE_REALM_OWNER,
                           realm_creation=True,acting_user=None,enable_marketing_emails=False)
if not owner.is_active or not owner.is_realm_owner or owner.is_bot:
    raise ValueError("Účet správce má jiného vlastníka nebo oprávnění")

channels = {}
for department,name in names.items():
    channel, _ = create_stream_if_needed(realm,name,invite_only=True,is_web_public=False,acting_user=owner)
    if channel.deactivated or not channel.invite_only or channel.is_web_public:
        raise ValueError("Kanál útvaru není aktivní a soukromý")
    channels[department] = channel
bulk_add_subscriptions(realm,channels.values(),[owner],acting_user=owner)
for code,display in sorted(employees.items()):
    email = f"ai-{code}-bot@polarita.test"
    channel = channels[code[:2]]
    bot = UserProfile.objects.filter(realm=realm,delivery_email__iexact=email).first()
    if bot is None:
        bot = do_create_user(email,None,realm,display,bot_type=UserProfile.DEFAULT_BOT,bot_owner=owner,
                             default_sending_stream=channel,default_events_register_stream=channel,
                             add_initial_stream_subscriptions=False,acting_user=owner)
    if not bot.is_active or not bot.is_bot or bot.bot_owner_id!=owner.id or bot.full_name!=display:
        raise ValueError("Kolize identity pracovního účtu "+code)
    bulk_add_subscriptions(realm,[channel],[bot],acting_user=owner)
    if not Subscription.objects.filter(user_profile=bot,recipient_id=channel.recipient_id,active=True).exists():
        raise ValueError("Chybí odběr kanálu pozice "+code)
print("Zulip potvrdil správce, osm soukromých kanálů útvarů a dvacet nativních botů s odběrem svého kanálu.")

monitor_email = "checkmk-bot@polarita.test"
monitor_channel = channels["17"]
monitor = UserProfile.objects.filter(realm=realm,delivery_email__iexact=monitor_email).first()
if monitor is None:
    monitor = do_create_user(monitor_email,None,realm,"Checkmk TEST",bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
                             bot_owner=owner,default_sending_stream=monitor_channel,
                             add_initial_stream_subscriptions=False,acting_user=owner)
if (not monitor.is_active or monitor.bot_owner_id != owner.id or monitor.bot_type != UserProfile.INCOMING_WEBHOOK_BOT
        or monitor.default_sending_stream_id != monitor_channel.id):
    raise RuntimeError("Neplatná identita příjmového bota Checkmk")
bulk_add_subscriptions(realm,[monitor_channel],[monitor],acting_user=owner)
if set(Subscription.objects.filter(user_profile=monitor,active=True,recipient__type=Recipient.STREAM)
       .values_list("recipient_id",flat=True)) != {monitor_channel.recipient_id}:
    raise RuntimeError("Nesouhlasí soukromý odběr monitoringu")

# Nativní příloha a zpráva ve vyhrazeném testovacím tématu pro kontrolu obnovy.
filename = "polarita-obnova-zulip-test-v1.txt"
sample = b"Polarita TEST Zulip 1\n"
records = Attachment.objects.filter(realm=realm, owner=owner, file_name=filename)
if not records.exists():
    url, _ = upload_message_attachment(filename, "text/plain", sample, owner)
    attachment = records.get(path_id=url.removeprefix("/user_uploads/"))
else:
    attachment = records.get()
if attachment.size != len(sample):
    raise ValueError("Kontrolní příloha má jiný obsah")
channel = channels["17"]
topic = "POL-2026-00000"
if not attachment.messages.filter(recipient_id=channel.recipient_id, subject=topic, sender=owner).exists():
    body = f"Zkouška obnovy týmového chatu. [Kontrolní soubor](/user_uploads/{attachment.path_id})"
    internal_send_stream_message(owner, channel, topic, body, acting_user=owner)
if not attachment.messages.filter(recipient_id=channel.recipient_id, subject=topic, sender=owner).exists():
    raise ValueError("Zulip nespojil kontrolní přílohu se zprávou v oddělení IT")
