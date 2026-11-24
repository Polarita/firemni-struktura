"""Tři neškodné přílohy pro ověření antiviru, oddělení cizího textu a rastrové kopie PDF."""
from hashlib import sha256
import io
import json
from pathlib import Path
import time
from xml.etree.ElementTree import fromstring
import prijem


def main():
    root = prijem.BASE
    sample = Path("/srv/polarita/workspace/dukazy/blok-04/pecet/predavaci-protokol.pdf").read_bytes()
    text = "Ověření TEST. Text přílohy obsahuje <štítek> & další znaky."
    # Standardní neškodný antivirový test EICAR.
    marker = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
    jobs = [prijem.enqueue(io.BytesIO(data), kind) for data, kind in
            ((sample, "pdf"), (text.encode(), "txt"), (marker, "txt"))]
    deadline = time.monotonic() + 720 + len(jobs)*1380
    last = -1
    while True:
        done = sum((root/"protokoly"/(job+".json")).is_file() for job in jobs)
        if done != last:
            print(f"Karanténa dokončila {done}/{len(jobs)} testovacích příloh.",flush=True)
            last = done
        if done == len(jobs):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("Fronta nedokončila testovací úlohy")
        time.sleep(5)
    reports = [json.loads((root/"protokoly"/(job+".json")).read_text()) for job in jobs]
    if [r["stav"] for r in reports] != ["ocisteno", "ocisteno", "odmitnuto"]:
        raise RuntimeError("Výsledek karantény: " + ", ".join(r["stav"] + "/" + r["duvod"] for r in reports))
    pdf = (root/"vysledky"/jobs[0]).read_bytes()
    if not pdf.startswith(b"%PDF") or sha256(sample).digest() == sha256(pdf).digest():
        raise RuntimeError("Nevznikla samostatná rekonstrukce PDF")
    node = fromstring((root/"vysledky"/(jobs[1][:-4]+".xml")).read_bytes())
    if node.tag != "untrusted_inbound_comm" or node.attrib != {"role": "external_data"} or len(node) or node.text != text:
        raise RuntimeError("Cizí text opustil datovou obálku")
    if reports[2]["duvod"] != "antivirovy-nalez" or (root/"vysledky"/(jobs[2][:-4]+".xml")).exists():
        raise RuntimeError("Antivirový vzorek prošel")
    for job, original, archive in zip(jobs,(sample,text.encode(),marker),("prijate","prijate","odmitnute")):
        stored = root / archive / job
        while not stored.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        if sha256(stored.read_bytes()).digest() != sha256(original).digest():
            raise RuntimeError("Kontrolní součet originálu nesouhlasí")
    print("Vzor PDF prošel antivirem a rastrovou rekonstrukcí v Dangerzone. Původní zapečetěný dokument zůstal dohledatelný.")
    print("Text zachoval svůj obsah v pasivní datové obálce. ClamAV zablokoval test EICAR a nevydal výstup.")
    print("Denní signatury ve zkoušce byly staré", reports[0]["signatury_hodin"], "hodin.")


if __name__ == "__main__":
    main()
