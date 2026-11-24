"""Technická evidence pro první servisní poptávku. Produkční listiny přebírá správce."""
from datetime import date
import sys

SOURCE = "https://eur-lex.europa.eu/legal-content/CS/ALL/?uri=CELEX%3A32016R0679"
DAY = date(2026, 11, 24)
FIELDS = {
    "predpis": ("04-Pravo-a-Smlouvy/den-1-registr-zdroje.md", "15001"),
    "metodika": ("03-Normy-a-Metodiky/den-1-metodika.md", "15002"),
    "minimum": ("04-Pravo-a-Smlouvy/den-1-pravni-minimum.md", "15001"),
}


def import_text(kind, source, text):
    if kind == "licencovany-vytah":
        raise PermissionError("V TEST není doloženo oprávnění k importu placeného textu.")
    if (kind, source) == ("bibliografie", SOURCE) and not text:
        return "Nařízení EU o ochraně osobních údajů, původní vydání. Úřední věstník EU L 119, strany 1–88."
    if kind == "vlastni-vzor" and source.startswith("repo:nasazeni/test/den-1/"):
        return text
    raise ValueError("Zdroj nepatří do testovací báze.")


def pages():
    fixture = "repo:nasazeni/test/den-1/baze.py"
    records = {
        "predpis": ("Bibliografický záznam pro servisní poptávku", SOURCE, date(2016, 4, 27),
                    "informační doložka", import_text("bibliografie", SOURCE, "")),
        "metodika": ("Metodika předání servisní poptávky", fixture, DAY, "předávací protokol",
                     import_text("vlastni-vzor", fixture,
                                 "U zkušebního spisu porovnej identifikátor v příjmu a v předávacím protokolu. "
                                 "Při neshodě vrať vzor kanceláři k doplnění.")),
        "minimum": ("Právní minimum Dne 1 pro evidenci servisní poptávky", fixture, DAY,
                    "testovací karta poptávky a informační doložka",
                    import_text("vlastni-vzor", fixture,
                                "Přijmi syntetickou poptávku do zkušebního spisu. Zaznamenej účel evidence "
                                "a odpovědnou roli. Přilož prázdný předávací protokol. Předání si může "
                                "správce vyzkoušet mezi kanceláří a technikou.\n\n"
                                "## Podklady k převzetí\n\n"
                                "Správce po převzetí určí skutečné činnosti, podmínky přístupu k normám, "
                                "ceník a vzory listin k posouzení advokátem. Pro technickou zkoušku slouží "
                                "šablony servisní smlouvy a informační doložky v balíčku S1.")),
    }
    result = {}
    for key, (title, source, version, impact, content) in records.items():
        path, role = FIELDS[key]
        result[path] = (f"# {title}\n\n**TEST · evidence servisní poptávky**\n\n{content}\n\n"
                        f"| Údaj | Hodnota |\n|---|---|\n| Zdroj | {source} |\n"
                        f"| Datum znění | {version} |\n| Kontrola podkladu TEST | {DAY} |\n"
                        f"| Stav | Vzor pro technické ověření |\n| Odpovědná role | {role} |\n| Dotčené výstupy | {impact} |\n")
    return result


if __name__ == "__main__":
    sys.path.insert(0, "/opt/polarita-agent-vault/current")
    from pamet import read, save, snapshot
    try:
        import_text("licencovany-vytah", "test:bez-licence", "syntetický obsah zkoušky")
    except PermissionError:
        pass
    else:
        raise RuntimeError("Import chráněného obsahu prošel bez licence.")
    entries = pages()
    rev = save(entries, "Vzor právní a normové báze prvního dne TEST")
    _, stored = snapshot()
    if any(read(stored[key]) != value for key, value in entries.items()):
        raise RuntimeError("Obsah čtený z Vaultu se liší od ověřeného vzoru.")
    print("Tři vzory v Gitu ověřeny, režim bez licence odmítl výtah. Revize", rev)
