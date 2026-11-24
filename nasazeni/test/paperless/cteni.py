"""Přidělí ověřenému účtu správce čtení českého testovacího protokolu."""
import os
import re
import sys

sys.path.insert(0, "/usr/src/paperless/src")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")
import django
django.setup()
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import Permission
from django.db import transaction
from documents.models import CustomFieldInstance, Document

case, checksum = sys.argv[1:]
if (os.getuid() != 1000 or not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", case)
        or not re.fullmatch(r"[a-f0-9]{64}", checksum)):
    raise RuntimeError("Neplatný zkušební spis")
with transaction.atomic():
    account = SocialAccount.objects.select_related("user").get(
        provider="keycloak", user__is_active=True, user__email="spravce@polarita.test")
    user = account.user
    if user.has_usable_password():
        raise RuntimeError("Archiv očekává testovací účet přihlášený pouze přes Keycloak")
    doc = Document.objects.select_for_update().get(checksum=checksum, title=f"{case} – Předávací protokol TEST")
    cf = CustomFieldInstance.objects.get(document=doc, field__name="case_id", value_text=case)
    if doc.owner_id not in (None, user.pk):
        raise RuntimeError("Zkušební protokol má jiného vlastníka")
    if doc.owner_id is None:
        doc.owner = user
        doc.save(update_fields=["owner"])
    for model in ("document", "customfield"):
        permission = Permission.objects.get(content_type__app_label="documents", codename="view_" + model)
        user.user_permissions.add(permission)
print(doc.pk, cf.field_id)
