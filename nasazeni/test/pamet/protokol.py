"""Uloží dokončený provozní test do znalostního Gitu a přečte jej účtem CEO v SHADOW."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path("/srv/polarita/workspace/dukazy")
CLI = "/usr/local/bin/agent_vault"
DOKLADY = {
    "08": {"vikunja", "sanony", "paperless-vzor", "paperless-prihlaseni", "paperless-cteni",
           "prenos-dokladu", "archiv-revize", "kniha-objektu", "kniha-prohlizec", "spisy-osa"},
    "09": {"umami", "web", "web-pristup", "web-prohlizec"},
}


def priprav(blok, nazev, revize, obsah):
    if not obsah.strip():
        raise ValueError("Zdrojový protokol je prázdný.")
    otisk = hashlib.sha256(obsah).hexdigest()
    klic = f"b{blok}-{nazev}-{revize[:12]}-{otisk[:16]}"
    popis = (f"Provozní zkouška TEST · blok {blok} · {nazev}\n\n"
             f"Zdrojová revize `{revize}`\n\n"
             f"SHA-256 zdroje `{otisk}`\n\n")
    # Závěrečný oddělovač uchová i původní zakončení řádků uvnitř záznamu.
    telo = popis.encode() + b"```text\n" + obsah + b"\n```"
    if len(telo) > 32768:
        raise ValueError("Provozní protokol přesahuje velikost předávky znalostního Gitu.")
    telo.decode("utf-8")
    return klic, telo, otisk


def zaznam(blok, nazev, revize):
    if nazev not in DOKLADY.get(blok, ()) or not re.fullmatch(r"[0-9a-f]{40}", revize):
        raise ValueError("Neznámý typ provozního testu nebo neplatná zdrojová revize.")
    cesta = ROOT / ("blok-" + blok) / f"{nazev}-{revize}.txt"
    with os.fdopen(os.open(cesta, os.O_RDONLY | os.O_NOFOLLOW), "rb") as f:
        obsah = f.read(32769)
    klic, telo, otisk = priprav(blok, nazev, revize, obsah)
    ulozeno = json.loads(subprocess.check_output([CLI, "log", klic], input=telo))
    stranka = ulozeno["cesta"]
    if stranka != f"08-Deniky-a-Predavky/log-instalace-{klic}.md":
        raise RuntimeError("Znalostní paměť vrátila neočekávanou cestu.")
    cteni = json.loads(subprocess.check_output(["runuser", "-u", "pol-vault-11001", "--",
                                                CLI, "get-context", stranka], stdin=subprocess.DEVNULL))
    hlavicka = f"# Předávka {klic}\n\nRole instalace\n\n".encode()
    if cteni["cesta"] != stranka or cteni["text"].encode() != hlavicka + telo + b"\n":
        raise RuntimeError("Čtecí účet získal jiný obsah než ve zdrojovém protokolu.")
    return {"cesta": stranka, "revize_vaultu": ulozeno["revize"], "sha256": otisk}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("blok", choices=sorted(DOKLADY))
    p.add_argument("revize")
    p.add_argument("doklady", nargs="+")
    args = p.parse_args()
    for doklad in args.doklady:
        print(json.dumps(zaznam(args.blok, doklad, args.revize), ensure_ascii=False), flush=True)
