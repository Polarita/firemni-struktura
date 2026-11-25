"""Ověření vydání tří cvičných metodik spravovaných ve znalostním Vaultu."""
from functools import cache
from hashlib import sha1, sha256
import json
from pathlib import Path
import re

from metodiky import nacti
from model import unique


SKUPINY = ("dlm", "vedeni", "lps")
ULOZISTE = Path("/opt/polarita-inzenyring-test/metodiky")
ODDELENI = "03-Normy-a-Metodiky"


def json_text(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)


def cesta(kod):
    if not isinstance(kod, str) or not re.fullmatch(r"SIM-[A-Z0-9-]+/[1-9][0-9]*", kod):
        raise ValueError("Neplatný kód nebo vydání zkušební metodiky.")
    return f"{ODDELENI}/projekt-{kod.lower().replace('/', '-v')}.md"


def stranka(metoda):
    return (f"# {metoda['kod']}\n\nTestovací metodika pro model {metoda['model']}. "
            f"Správce báze 15002 normovac. Platnost od {metoda['od']} do {metoda['do']}.\n\n"
            "Parametry modelu TEST\n\n" + "```json\n" + json_text(metoda) + "\n```\n")


@cache
def vydani():
    stranky = {}
    for skupina in SKUPINY:
        metody = nacti(skupina + "-metodiky-test.json")
        if not metody:
            raise ValueError("Prázdná větev registru.")
        for metoda in metody:
            path = cesta(metoda["kod"])
            if path in stranky or metoda["ucel"] != "simulace":
                raise ValueError("Kolize označení nebo nepřípustný účel metodiky.")
            stranky[path] = (skupina, stranka(metoda))
    verze = sha256(json_text(stranky).encode()).hexdigest()
    return verze, stranky


def over(balik):
    verze, ocekavane = vydani()
    if balik["vydani"] != verze or set(balik["stranky"]) != set(ocekavane):
        raise ValueError("Čtecí kopie neodpovídá vydání projektových metodik.")
    registr = {s: [] for s in SKUPINY}
    podklady = {}
    for path, (skupina, vzor) in ocekavane.items():
        page = balik["stranky"][path]
        raw = page["text"].encode()
        blob = b"blob " + str(len(raw)).encode() + b"\0" + raw
        if (page["text"] != vzor or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", page["revize"])
                or len(page["revize"]) != len(page["objekt"])
                or page["objekt"] != (sha1(blob) if len(page["objekt"]) == 40 else sha256(blob)).hexdigest()):
            raise ValueError("Znění, revize nebo objekt stránky nesouhlasí s vydáním.")
        obsah = page["text"].split("\n```json\n", 1)[1].removesuffix("\n```\n")
        metoda = json.loads(obsah, object_pairs_hook=unique)
        registr[skupina].append(metoda)
        podklady[metoda["kod"]] = {"cesta":path, "revize":page["revize"], "objekt":page["objekt"],
                                  "sha256":sha256(raw).hexdigest(), "text":page["text"]}
    return registr, podklady


def nacti_bazi():
    path = ULOZISTE / vydani()[0] / "registr.json"
    zaznam = json.loads(path.read_bytes(), object_pairs_hook=unique)
    balik = zaznam["registr"]
    if sha256(json_text(balik).encode()).hexdigest() != zaznam["sha256"]:
        raise ValueError("Kontrolní součet čtecí kopie se změnil.")
    return over(balik)
