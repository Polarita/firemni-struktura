# Záznam o ověření generátoru čistopisů (balíček S1 · Verze 2.8)

- **Datum běhu:** 19. 11. 2026 (Windows, `Python 3.11.16`, `markdown 3.11.3`, `pypdf 7.1.1`, headless Chrome)
- **Příkaz:** `uv run --with markdown --with pypdf python generate_pdfs.py` → návratový kód `0`, **`15` dokumentů v `8` sestavách, `69` stran** (`generate_pdfs.py --check` → `VERIFIED_PASS: 15/15`)
- **Testy:** `uv run --with markdown --with pypdf python test_generate_pdfs.py` → `OK` (`8` testů včetně tisku zkušebního PDF, escapování HTML a zneškodnění značek v dosazovaných hodnotách)
- **Co kontrola pokrývá:** úplnost proměnných šablona ↔ data oběma směry, platná hlavička PDF, žádná nevyplněná proměnná v textu PDF, manifest s otisky `SHA-256`; v textu vygenerovaných PDF není žádné číslo předpisu, paragrafu ani označení normy.
- **Co kontrola nepokrývá:** právní a normovou správnost textů. Šablony jsou ukázkové vzory bez odkazů na konkrétní předpisy a normy; skutečné znění sestaví `15001 pravni-specialista` až po nasazení systému z právní báze a zreviduje advokát. Nepokrývá ani běh v zóně `sandbox_airgap`.
- Všechna PDF v této složce nesou vodoznak **VZOR** a obsahují fiktivní data.

| Soubor | Název dokumentu | Proměnných | Stran | SHA-256 PDF |
| :--- | :--- | ---: | ---: | :--- |
| `01-smlouva-o-dilo.pdf` | Smlouva o dílo — elektromontáže, FVE, EV wallboxy a LPS | 46 | 7 | `5df35422a457bb73…` |
| `01a-zmenovy-list-vicepraci.pdf` | Změnový list víceprací a méněprací | 47 | 3 | `5caf1c1c380ba545…` |
| `02-pausalni-servisni-smlouva-mrr.pdf` | Paušální servisní smlouva „Elektro Správa SVJ a Firem“ | 54 | 6 | `9f35956607603737…` |
| `03-ramcova-smlouva-certified-partner-sub.pdf` | Rámcová smlouva o spolupráci — Certified Partner SUB | 46 | 6 | `82423882458d3088…` |
| `04a-dohoda-odpovednost-sverene-hodnoty-van.pdf` | Dohoda o odpovědnosti k ochraně hodnot svěřených zaměstnanci k vyúčtování — pojízdný sklad | 15 | 3 | `5ca9232039adecdb…` |
| `04b-dohoda-svereni-sluzebniho-vozidla.pdf` | Dohoda o svěření služebního vozidla a pravidla jeho užívání | 23 | 5 | `a1e84a9e115d7d75…` |
| `04c-dohoda-sverene-predmety-meridla-oopp.pdf` | Dohoda o odpovědnosti za ztrátu svěřených věcí — měřicí přístroje, OOPP a nářadí | 32 | 4 | `454ee0ce7480c214…` |
| `05a-vyrobni-pas-rozvadece.pdf` | Výrobní pas rozváděče | 95 | 8 | `81ba363456a939e3…` |
| `05b-protokol-kusove-zkousky.pdf` | Protokol o kusovém ověření rozváděče | 62 | 4 | `213951b2871ae005…` |
| `05c-eu-prohlaseni-o-shode.pdf` | EU prohlášení o shodě | 27 | 3 | `aa0e065f95e244ec…` |
| `06a-nouzova-plna-moc.pdf` | Nouzová omezená provozní plná moc (režim Break-Glass) | 21 | 4 | `702c54c28720ed26…` |
| `06b-protokol-break-glass.pdf` | Protokol o aktivaci a ukončení režimu Break-Glass | 92 | 4 | `6a2570a07742d671…` |
| `07-predzalobni-vyzva.pdf` | Předžalobní výzva k plnění | 43 | 4 | `c54c7a21b0299da1…` |
| `08a-smernice-monitoring-komunikace.pdf` | Vnitřní směrnice o monitoringu firemních komunikačních prostředků a nahrávání hovorů | 12 | 5 | `c8a176262da0fc85…` |
| `08b-informacni-dolozka-zamestnance.pdf` | Informační doložka o monitoringu firemních komunikačních prostředků a nahrávání hovorů | 14 | 3 | `045e08b5d94fb837…` |
