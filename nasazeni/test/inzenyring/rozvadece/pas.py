"""Vydání modelového výrobního pasu pro sériové číslo přidělené ve spisu."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys

from teplota import posud

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "revize"))
from instaluj import run, WORK
from publikace import publikuj
from spisy_rz import VARIANTY, id_spisu

S1 = HERE.parents[3] / "balicky/S1-generator-cistopisu/data"
PDF = "vyrobni-pas.pdf"
KODY = ("pevnost_materialu kryti vzdalenosti ochrana_pred_urazem vestavba vnitrni_obvody "
        "svorky dielektricke otepleni zkratova_odolnost emc mechanicka_funkce").split()
KUS = "kryti vzdalenosti ochrana_pred_urazem vestavba vnitrni_obvody svorky mechanicka_funkce dielektricke zapojeni_a_funkce".split()
QR = """import sys, zxingcpp
code = zxingcpp.create_barcode(sys.argv[1], zxingcpp.BarcodeFormat.QRCode)
print(zxingcpp.write_barcode_to_svg(code))
"""


def model():
    nacti = lambda cesta: json.loads(cesta.read_bytes())
    pas = nacti(S1 / "05a-vyrobni-pas-rozvadece.json")
    kus = nacti(S1 / "05b-protokol-kusove-zkousky.json")
    eu = nacti(S1 / "05c-eu-prohlaseni-o-shode.json")
    podklady = nacti(HERE / "osazeni-test.json")
    metodika = nacti(HERE / "metodika-test.json")
    prvky = {pas[f"pristroj_{i}_oznaceni"]: (pas[f"pristroj_{i}_popis"], pas[f"pristroj_{i}_sn"]) for i in range(1,6)}
    for dokument in (kus, eu):
        for field in ("typ_rozvadece", "vyrobni_cislo", "spis_id", "cislo_pasu", "jmenovity_proud_ina", "jmenovite_napeti_un", "stupen_kryti_ip"):
            if dokument[field] != pas[field]:
                raise ValueError("Podklady S1 patří různým výrobkům.")
    if any(kus["vysledek_"+k] != "VYHOVUJE" or not kus["poznamka_"+k].strip() for k in KUS):
        raise ValueError("Kusové ověření vzoru je neúplné nebo záporné.")
    navrh = [{"bod":k.replace("_"," "), "zapis":pas["overeni_"+k]} for k in KODY]
    if not all(row["zapis"].strip() for row in navrh):
        raise ValueError("Chybí údaj ověření návrhu.")
    return {"typ":pas["typ_rozvadece"], "skrin":pas["skrinovy_system"], "napeti":pas["jmenovite_napeti_un"],
            "proud":pas["jmenovity_proud_ina"], "kryti":pas["stupen_kryti_ip"], "okoli":podklady["okoli_C"],
            "pouziti":eu["urcene_pouziti"], "edice":metodika["edice"], "den":podklady["den_posouzeni"],
            "pravidla":metodika["pravidla"], "teplo":posud(metodika, podklady, prvky), "navrh":navrh,
            "prvky":[{**p,"popis":prvky[p["oznaceni"]][0],"sn":prvky[p["oznaceni"]][1]} for p in podklady["pristroje"]],
            "kus":[{"bod":k.replace("_"," "), "zapis":kus["vysledek_"+k]+" · "+kus["poznamka_"+k]} for k in KUS]}


def vydej(host):
    common = model()
    WORK.mkdir(parents=True, exist_ok=True)
    for variant in VARIANTY:
        uid = str(id_spisu(variant))
        sql = f"""SELECT v.case_id, v.vyrobni_cislo FROM polarita_test_spisy.vyrobni_cisla v
                  JOIN polarita_test_spisy.karty k USING(case_id) WHERE k.pozadavek='{uid}' AND v.oznaceni='RP1';"""
        result = run("postgres-test", "runuser","-u","pol_metadata_read","--","psql","-XAtqw","-v","ON_ERROR_STOP=1",
                     "-d","db_erp_lhutnik","-c",sql).decode().strip()
        match = re.fullmatch(r"(POL-[0-9]{4}-[0-9]{5})\|(RZ-[0-9]{4}-[0-9]{5})", result)
        if not match:
            raise ValueError("Chybí jednoznačné výrobní číslo dílenského kusu ve spisu.")
        case, serial = match.groups()
        url = f"https://{host}/lhutnik-test/spisy?spis={case}&oddil=kniha"
        svg = run("paperless-test","python3","-c",QR,url,user="65534").decode()
        data = dict(common, spis=case, cislo=serial, oznaceni="RP1", qr=svg)
        pdf = run("reditelstvi-test", "/usr/local/bin/polarita-typst","compile","--ignore-system-fonts","--creation-timestamp","0",
                  "--root","/usr/local/share/polarita-revize-test","--input","model="+json.dumps(data,ensure_ascii=False),
                  "-","-",user="65534",data=(HERE/"pas.typ").read_bytes())
        scan = run("paperless-test","python3","/usr/local/share/polarita-qr.py",user="65534",data=pdf).decode().strip()
        if scan != url:
            raise ValueError("QR na vytištěném štítku neotevírá knihu správného spisu.")
        over_strany(pdf, serial, case)
        digest = hashlib.sha256(pdf).hexdigest()
        info = {"vyrobni_cislo":serial, "case_id":case, "pdf_sha256":digest, "kniha":scan,
                "strany":5, "stav":"navrh-test", "predani_do_provozu":False}
        files = {PDF:pdf, "prehled.json":json.dumps(info, ensure_ascii=False, sort_keys=True).encode()}
        base = f"/opt/polarita-inzenyring-test/pasy/{uid}/{serial}"
        publikuj(run, "postgres-test", base, files, WORK)
        print(case, serial, digest, scan, flush=True)


def over_strany(pdf, serial, case):
    from io import BytesIO
    from over_tisk import WHEEL, SHA
    if hashlib.sha256(WHEEL.read_bytes()).hexdigest() != SHA:
        raise ValueError("Otisk čtečky PDF nesouhlasí.")
    sys.path.insert(0, str(WHEEL))
    from pypdf import PdfReader
    from unicodedata import normalize
    pages = PdfReader(BytesIO(pdf)).pages
    titles = ("Tisková předloha štítku CE","Výrobní pas rozváděče","Protokol ověření návrhu",
              "Protokol kusového ověření","Návrh EU prohlášení o shodě")
    for page,title in zip(pages,titles,strict=True):
        content = normalize("NFC"," ".join(page.extract_text().split())).replace("\u00ad","")
        if any(t not in content for t in (case, serial, title, "TEST")):
            raise ValueError("Vysázená strana neodpovídá spisu a pořadí dokladů.")


if __name__ == "__main__":
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq" or not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", sys.argv[1]):
        raise SystemExit("Vydání patří do virtuálního stroje polarita-hq TEST.")
    with open("/run/polarita-vyrobni-pasy-test.lock","a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        vydej(sys.argv[1])
