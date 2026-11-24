"""V rámci zkoušky použije běžnou frontu importu Paperless a načte dokument i s vazbou na spis."""
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import unicodedata
import uuid

sys.path.insert(0, "/usr/src/paperless/src")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")
import django
django.setup()
from django.conf import settings
from documents.data_models import ConsumableDocument, DocumentMetadataOverrides, DocumentSource
from documents.models import CustomField, CustomFieldInstance, Document, PaperlessTask
from documents.tasks import consume_file

case, checksum = sys.argv[1:]
if os.getuid() != 1000 or not re.fullmatch(r"POL-[0-9]{4}-[0-9]{5}", case) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
    raise RuntimeError("Neplatná zkouška archivu")
data = sys.stdin.buffer.read(128 * 1024**2 + 1)
if len(data) > 128 * 1024**2 or not data.startswith(b"%PDF") or hashlib.sha256(data).hexdigest() != checksum:
    raise RuntimeError("Přenesený obsah se liší od výstupu karantény")
field, _ = CustomField.objects.get_or_create(name="case_id", defaults={"data_type": CustomField.FieldDataType.STRING})
if field.data_type != CustomField.FieldDataType.STRING:
    raise RuntimeError("Pole case_id má jiný datový typ")
title = f"{case} – Předávací protokol TEST"
doc = Document.objects.filter(checksum=checksum).first()
attempt = 0
while True:
    task_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"polarita.test/archiv/{case}/{checksum}/{attempt}"))
    task = PaperlessTask.objects.filter(task_id=task_id).first()
    if task is None or task.status not in (PaperlessTask.Status.FAILURE, PaperlessTask.Status.REVOKED):
        break
    attempt += 1
if doc is None and task is None:
    folder = Path(tempfile.mkdtemp(prefix="polarita-vzor-", dir=settings.SCRATCH_DIR))
    pdf = folder / "predavaci-protokol.pdf"
    pdf.write_bytes(data)
    consume_file.apply_async(task_id=task_id, kwargs={
        "input_doc": ConsumableDocument(source=DocumentSource.ApiUpload, original_file=pdf),
        "overrides": DocumentMetadataOverrides(filename=pdf.name, title=title, custom_fields={str(field.pk): case}),
    }, headers={"trigger_source": PaperlessTask.TriggerSource.API_UPLOAD})
deadline = time.monotonic() + 1650
while doc is None and time.monotonic() < deadline:
    if PaperlessTask.objects.filter(task_id=task_id, status__in=[PaperlessTask.Status.FAILURE, PaperlessTask.Status.REVOKED]).exists():
        raise RuntimeError("Úloha OCR protokolu skončila chybou")
    time.sleep(5)
    doc = Document.objects.filter(checksum=checksum).first()
if doc is None or doc.title != title or not CustomFieldInstance.objects.filter(document=doc, field=field, value_text=case).exists():
    raise RuntimeError("Chybí zkušební protokol s vazbou na spis")
text = "".join(c for c in unicodedata.normalize("NFKD", doc.content.lower()) if not unicodedata.combining(c))
if not all(word in text for word in ("protokol", "svitidlo")):
    raise RuntimeError("OCR nepřečetlo očekávaný obsah čistého PDF")
print(f"Paperless uložil dokument {doc.pk} ke spisu {case} a přečetl rastrový protokol z karantény.", flush=True)
