"""Sestaví předávací zprávu správci z protokolů jedné revize TEST."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile

ROOT = Path("/srv/polarita/workspace/dukazy")
DOKLADY = (
    ("00", "vstupy-test", "json", "Vstupní údaje instalace"),
    ("01", "inventura", "json", "Inventura prostředí"),
    ("02", "topologie", "txt", "Topologie vnitřní sítě"),
    ("03", "zkouska-vpn", "txt", "Přístup přes firemní VPN"),
    ("04", "pecet", "txt", "Testovací pečeť"),
    ("05", "gitea", "txt", "Firemní Git"),
    ("06", "dohled", "txt", "Sběr provozních údajů"),
    ("06", "restic", "txt", "Zkouška zálohy"),
    ("07", "metadata", "txt", "Metadata firemních služeb"),
    ("08", "prenos-dokladu", "txt", "Předání vzorového dokladu"),
    ("09", "eshop-objednavka", "txt", "Objednávka ve vzorovém e-shopu"),
    ("10", "cad-vykresy", "txt", "Zpracování výkresů"),
    ("11", "registr-dokladu", "txt", "Registr dokladů"),
    ("11", "provize", "txt", "Výpisy ČS a Fio, párování UOL a partnerské provize"),
    ("12", "vstup-predani", "txt", "Závěrečné přihlášení správce a odkazy na služby"),
)


def sestav(root, revize, domena):
    if not re.fullmatch(r"[0-9a-f]{40}", revize):
        raise ValueError("Zadejte úplnou zdrojovou revizi.")
    if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", domena):
        raise ValueError("Zadejte DNS jméno portálu ve VPN.")
    radky = []
    chybi = []
    for blok, nazev, pripona, popis in DOKLADY:
        cesta = Path(f"blok-{blok}") / f"{nazev}-{revize}.{pripona}"
        try:
            with os.fdopen(os.open(root / cesta, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as f:
                info = os.fstat(f.fileno())
                if not stat.S_ISREG(info.st_mode) or not info.st_size:
                    raise ValueError(f"Neplatný nebo prázdný protokol {cesta}")
                otisk = hashlib.file_digest(f, "sha256").hexdigest()
        except FileNotFoundError:
            chybi.append(str(cesta))
            radky.append(f"Čeká se na protokol • {popis}\n  {cesta}")
        else:
            radky.append(f"Doloženo • {popis}\n  {cesta}\n  {info.st_size} B · SHA-256 {otisk}")
    stav = "Průběžný přehled, čeká se na protokoly" if chybi else "Vybrané technické zkoušky jsou doloženy"
    obsah = [
        "Ředitelství Polarity – předávací zpráva pro správce (TEST)",
        f"Revize {revize}", stav, "",
        f"Ve firemní VPN otevřete https://{domena}/ a přihlaste se jako spravce.",
        "Použijte testovací heslo přidělené při instalaci.",
        "Vyzkoušejte pracovní postupy se vzorovými daty a zaznamenejte výsledek převzetí.",
        "Produkční identity a osobní klíče přijdou na řadu po testování a převzetí správcem.",
        "", "Rozsah doložených technických zkoušek", *radky, "",
        "Uživatelské převzetí a rozhodnutí o produkčním provozu eviduje správce samostatně.", "",
    ]
    return "\n".join(obsah), chybi


def uloz(root, revize, domena):
    obsah, chybi = sestav(root, revize, domena)
    if chybi:
        raise ValueError("Předání čeká na protokoly: " + ", ".join(chybi))
    cesta = root / "blok-12" / f"predani-spravci-{revize}.txt"
    with tempfile.NamedTemporaryFile(dir=cesta.parent, delete=False) as f:
        try:
            f.write(obsah.encode())
            f.flush()
            os.replace(f.name, cesta)
        finally:
            Path(f.name).unlink(missing_ok=True)
    return cesta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revize")
    parser.add_argument("domena")
    parser.add_argument("--prehled", action="store_true", help="Vypíše průběžný stav bez uložení.")
    args = parser.parse_args()
    if args.prehled:
        print(sestav(ROOT, args.revize, args.domena)[0], end="")
    else:
        print(uloz(ROOT, args.revize, args.domena))
