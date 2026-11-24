"""Připraví organizační registr a provozní části osmi chart pro znalostní Git."""
import json
from pathlib import Path
import re
import sys
from pamet import save

def prepare(source, seed):
    data = json.loads((source/"nastroje/kanon.json").read_text())
    roles = [{k: agent[k] for k in ("id","sysid","department")} for agent in data["agents"]]
    (seed/"nastroje").mkdir()
    (seed/"oddeleni").mkdir()
    (seed/"nastroje/kanon.json").write_text(json.dumps({"agents":roles,"company":{"branch":data["company"]["branch"]}}))
    for number in range(11,19):
        doc, = (source/"oddeleni").glob(f"{number}-*.md")
        original = doc.read_text()
        intro, body = original.split("<!-- vault:provoz -->")
        body, _ = body.split("<!-- /vault:provoz -->")
        if not all(marker in body for marker in ("## ", "KPI", "**Hlavní vstupy", "**Hlavní výstupy")):
            raise ValueError(f"Neúplná provozní charta útvaru {number}")
        (seed/"oddeleni"/doc.name).write_text(intro.splitlines()[0]+"\n\n"+body.strip()+"\n")

def pages(source):
    canon = json.loads((source/"nastroje/kanon.json").read_text())
    team = canon["agents"]
    entries = {}
    purposes = [
        "Strategické vedení společnosti, koordinace odborných útvarů a evidence rozhodnutí.",
        "Měření návratnosti reklam, růst poptávek a tvorba obsahu.",
        "Provoz internetového obchodu, nákup zboží a skladová logistika.",
        "Projektování elektroinstalací, rozpočty, montáž, revize a odborná výuka.",
        "Nezávislé ověřování smluv, předpisů a technických norem.",
        "Účetní podklady, faktury, rozpočty, podatelna a sledování lhůt.",
        "Správa serverů, software, provoz ai, bezpečnost, zálohy a obnova dat.",
        "Personální kapacity, školení bezpečnosti práce a kvalifikace terénního týmu.",
    ]
    for number, purpose in enumerate(purposes,11):
        doc, = (source/"oddeleni").glob(f"{number}-*.md")
        heading, body = doc.read_text().split("\n\n", 1)
        title = heading.split(" — ",1)[1].split(" · Verze ",1)[0]
        roles = [(a["id"],a["sysid"]) for a in team if a["department"]==str(number)]
        if not roles or any(not re.fullmatch(str(number)+r"\d{3}",i) or not re.fullmatch("[a-z0-9-]+",r) for i,r in roles):
            raise ValueError("Neplatná karta útvaru")
        entries[f"02-Oddeleni-a-Procesy/utvar-{number}.md"] = (
            f"# Útvar {number} — {title}\n\n{purpose}\n\n## Role\n\n"
            +"\n".join(f"- {i} {r}" for i,r in roles)+f"\n\nZdroj v návrhu firmy je `oddeleni/{doc.name}`.\n")
        entries[f"02-Oddeleni-a-Procesy/charta-{number}.md"] = (
            f"# Provozní charta útvaru {number} — {title}\n\n{purpose}\n\n"
            f"Role jsou na stránce [[02-Oddeleni-a-Procesy/utvar-{number}]].\n\n"+body)
    if len(team)!=20 or canon["company"]["branch"]!="CZ-101":
        raise ValueError("Nesouhlasí organizační registr")
    entries["00-Meta/pobocky.md"] = "# Registr poboček\n\n| Číslo | Kód | Místo | Funkce |\n|---|---|---|---|\n| 101 | CZ-101 | Praha | Centrála |\n"
    entries["08-Deniky-a-Predavky/sablona-predavky.md"] = "# Šablona předání práce\n\n## Dokončená práce\n\n## Ověření a podklady\n\n## Další krok\n\n## Přebírající role\n"
    return entries

if __name__ == "__main__":
    if sys.argv[1:2] == ["--priprav"]:
        prepare(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        print(save(pages(Path(sys.argv[1])),"Založení osmi útvarů, registru poboček a šablony předání",update_seed=True))
