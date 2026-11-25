"""Vydání modelového výrobního pasu pro sériové číslo přidělené ve spisu."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
from uuid import UUID
import sys

from teplota import posud

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "revize"))
from publikace import WORK, publikuj, run
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


def rozvadec_spisu(uid):
    uid = str(UUID(uid))
    sql = f"""SELECT v.case_id, v.vyrobni_cislo FROM polarita_test_spisy.vyrobni_cisla v
              JOIN polarita_test_spisy.karty k USING(case_id) WHERE k.pozadavek='{uid}' AND v.oznaceni='RP1';"""
    result = run("postgres-test", "runuser","-u","pol_metadata_read","--","psql","-XAtqw","-v","ON_ERROR_STOP=1",
                 "-d","db_erp_lhutnik","-c",sql).decode().strip()
    match = re.fullmatch(r"(POL-[0-9]{4}-[0-9]{5})\|(RZ-[0-9]{4}-[0-9]{5})", result)
    if not match:
        raise ValueError("Chybí jednoznačné výrobní číslo dílenského kusu ve spisu.")
    return match.groups()


def nacti_vydani(uid, host):
    case, serial = rozvadec_spisu(uid)
    base = f"/opt/polarita-inzenyring-test/pasy/{uid}/{serial}"
    def cti(*args):
        return run("postgres-test", "runuser", "-u", "pol_metadata_read", "--", *args)
    # Obě čtení musí pocházet ze stejného neměnného vydání.
    rev = cti("readlink", base+"/current").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", rev):
        raise ValueError("Chybí připnuté vydání pasu.")
    adresar = base+"/"+rev+"/"
    raw_info = cti("cat", adresar+"prehled.json")
    info = json.loads(raw_info)
    pdf = cti("cat", adresar+PDF)
    url = f"https://{host}/lhutnik-test/spisy?spis={case}&oddil=kniha"
    sums = (hashlib.sha256(pdf).hexdigest()+"  "+PDF+"\n"+
            hashlib.sha256(raw_info).hexdigest()+"  prehled.json\n").encode()
    if hashlib.sha256(sums).hexdigest() != rev or cti("cat", adresar+"SHA256SUMS") != sums:
        raise ValueError("Obsah pasu nesouhlasí s neměnným vydáním.")
    if info != {"case_id":case, "vyrobni_cislo":serial, "strany":5, "stav":"navrh-test",
                "predani_do_provozu":False, "kniha":url, "pdf_sha256":hashlib.sha256(pdf).hexdigest()}:
        raise ValueError("Vydaný výrobní pas nebo jeho vazba na konkrétní kus nesouhlasí.")
    den = over_pdf(pdf, serial, case, url)
    return {**info, "den":den, "vydani":rev}


def over_pdf(pdf, serial, case, url):
    scan = run("paperless-test", "python3", "/usr/local/share/polarita-qr.py", user="65534", data=pdf).decode().strip()
    if scan != url:
        raise ValueError("QR na vytištěném štítku neotevírá knihu správného spisu.")
    return over_strany(pdf, serial, case)


def vydej(host):
    db = "postgres-test"
    run("reditelstvi-test", "install","-dm0755","/usr/local/share/polarita-revize-test")
    code = "/opt/polarita-inzenyring-test/rozvadece"
    run(db,"install","-dm0755",code)
    serials = HERE/"cisla.py"
    subprocess.run(["incus","file","push","--mode=0644",str(serials),db+code+"/cisla.py.next"],check=True)
    run(db,"mv","-T",code+"/cisla.py.next",code+"/cisla.py")
    print(run(db,"python3",code+"/cisla.py",*(str(id_spisu(v)) for v in VARIANTY)).decode(),end="",flush=True)
    common = model()
    WORK.mkdir(parents=True, exist_ok=True)
    for variant in VARIANTY:
        uid = str(id_spisu(variant))
        case, serial = rozvadec_spisu(uid)
        url = f"https://{host}/lhutnik-test/spisy?spis={case}&oddil=kniha"
        svg = run("paperless-test","python3","-c",QR,url,user="65534").decode()
        data = dict(common, spis=case, cislo=serial, oznaceni="RP1", qr=svg)
        pdf = run("reditelstvi-test", "/usr/local/bin/polarita-typst","compile","--ignore-system-fonts","--creation-timestamp","0",
                  "--root","/usr/local/share/polarita-revize-test","--input","model="+json.dumps(data,ensure_ascii=False),
                  "-","-",user="65534",data=(HERE/"pas.typ").read_bytes())
        if over_pdf(pdf, serial, case, url) != common["den"]:
            raise ValueError("Pas obsahuje jiné datum posouzení.")
        digest = hashlib.sha256(pdf).hexdigest()
        info = {"vyrobni_cislo":serial, "case_id":case, "pdf_sha256":digest, "kniha":url,
                "strany":5, "stav":"navrh-test", "predani_do_provozu":False}
        files = {PDF:pdf, "prehled.json":json.dumps(info, ensure_ascii=False, sort_keys=True).encode()}
        base = f"/opt/polarita-inzenyring-test/pasy/{uid}/{serial}"
        publikuj(run, "postgres-test", base, files, WORK)
        print(case, serial, digest, url, flush=True)


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
    den = None
    for page,title in zip(pages,titles,strict=True):
        content = normalize("NFC"," ".join(page.extract_text().split())).replace("\u00ad","")
        required = [case, serial, title, "TEST"]
        if title == "Výrobní pas rozváděče":
            datum = re.findall(r"Modelový den posouzení ([0-9]{4}-[0-9]{2}-[0-9]{2})", content)
            if len(datum) != 1:
                raise ValueError("V pasu chybí jednoznačný den posouzení.")
            den, = datum
        if any(t not in content for t in required):
            raise ValueError("Vysázená strana neodpovídá spisu a pořadí dokladů.")
    return den


if __name__ == "__main__":
    if os.geteuid() or socket.gethostname().split(".")[0] != "polarita-hq" or not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", sys.argv[1]):
        raise SystemExit("Vydání patří do virtuálního stroje polarita-hq TEST.")
    with open("/run/polarita-vyrobni-pasy-test.lock","a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        vydej(sys.argv[1])
