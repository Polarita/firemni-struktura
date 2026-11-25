"""Ověří, že obsah PDF, čísla měřidel a seznam závad odpovídají posouzení."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
import unicodedata

WHEEL = Path("/srv/polarita/infra/gitea-runner-test/podklady/wheels/pypdf-7.1.1-py3-none-any.whl")
SHA = "04c5680d4b4cfa04ab505b09393fc949860c34a4dad6565284d11a2f5c3ce8b1"


def overit(raw, model):
    if sha256(WHEEL.read_bytes()).hexdigest() != SHA:
        raise ValueError("Nesouhlasí otisk čtečky PDF.")
    if str(WHEEL) not in sys.path:
        sys.path.insert(0, str(WHEEL))
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(raw))
    text = " ".join(" ".join(page.extract_text() for page in reader.pages).split())
    text = unicodedata.normalize("NFC", text).replace("\u00ad", "")
    positive = model["stav"] == "navrh-kladny"
    title = "SCHOPNO" if positive else "NESCHOPNO"
    required = [f"NÁVRH — {title} BEZPEČNÉHO PROVOZU", model["spis"], model["projekt"], model["metodika"],
                "Předání do provozu je zablokované.", model["pas"]["vyrobni_cislo"], model["pas"]["pdf_sha256"]]
    for row in model["vysledky"]:
        required.extend((row["bod"], row["pristroj"], row["kalibracni_list"], row["hodnota"]+" "+row["jednotka"]))
        if not row["vyhovel"]:
            required.extend(("Zjištěné závady", row["ustanoveni"], row["navrh_lhuty"]))
    if not reader.pages or any(t not in text for t in required) or (positive and "NESCHOPNO" in text):
        raise ValueError("Obsah vysázeného PDF neodpovídá modelu revize.")
    return len(reader.pages)
