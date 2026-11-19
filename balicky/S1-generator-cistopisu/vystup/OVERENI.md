# Záznam o ověření generátoru čistopisů (balíček S1 · Verze 2.6)

- **Datum běhu:** 15. 11. 2026 (Windows 11, Python 3.12.10, `markdown`, `pypdf`, headless Chrome)
- **Příkaz:** `python generate_pdfs.py` → návratový kód `0`, **15 dokumentů v 8 sestavách, 69 stran**
- **Testy:** `python -m unittest test_generate_pdfs` → `OK` (7 testů včetně tisku zkušebního PDF a zneškodnění značek v dosazovaných hodnotách)
- **Co kontrola pokrývá:** úplnost proměnných šablona ↔ data oběma směry, platná hlavička PDF, žádná nevyplněná proměnná v textu PDF, manifest s otisky `SHA-256`; v textu vygenerovaných PDF není žádné číslo předpisu, paragrafu ani označení normy.
- **Co kontrola nepokrývá:** právní a normovou správnost textů. Šablony jsou ukázkové vzory bez odkazů na konkrétní předpisy a normy; skutečné znění sestaví `15001 pravni-specialista` až po nasazení systému z právní báze a zreviduje advokát. Nepokrývá ani běh v zóně `sandbox_airgap`.
- Všechna PDF v této složce nesou vodoznak **VZOR** a obsahují fiktivní data.

| Soubor | Název dokumentu | Proměnných | Stran | SHA-256 PDF |
| :--- | :--- | ---: | ---: | :--- |
| `01-smlouva-o-dilo.pdf` | Smlouva o dílo — elektromontáže, FVE, EV wallboxy a LPS | 46 | 7 | `04fd5243c44986ce…` |
| `01a-zmenovy-list-vicepraci.pdf` | Změnový list víceprací a méněprací | 47 | 3 | `761581e3602df982…` |
| `02-pausalni-servisni-smlouva-mrr.pdf` | Paušální servisní smlouva „Elektro Správa SVJ a Firem“ | 54 | 6 | `0b240c49a1b58683…` |
| `03-ramcova-smlouva-certified-partner-sub.pdf` | Rámcová smlouva o spolupráci — Certified Partner SUB | 46 | 6 | `c60bc7f73db2fce9…` |
| `04a-dohoda-odpovednost-sverene-hodnoty-van.pdf` | Dohoda o odpovědnosti k ochraně hodnot svěřených zaměstnanci k vyúčtování — pojízdný sklad | 15 | 3 | `1b134aab0dfadb7c…` |
| `04b-dohoda-svereni-sluzebniho-vozidla.pdf` | Dohoda o svěření služebního vozidla a pravidla jeho užívání | 23 | 5 | `65ab2a6839c426c8…` |
| `04c-dohoda-sverene-predmety-meridla-oopp.pdf` | Dohoda o odpovědnosti za ztrátu svěřených věcí — měřicí přístroje, OOPP a nářadí | 32 | 4 | `e6d93242782e7e9c…` |
| `05a-vyrobni-pas-rozvadece.pdf` | Výrobní pas rozváděče | 95 | 8 | `99d393541fd89215…` |
| `05b-protokol-kusove-zkousky.pdf` | Protokol o kusovém ověření rozváděče | 62 | 4 | `4d352b2c279ef6ab…` |
| `05c-eu-prohlaseni-o-shode.pdf` | EU prohlášení o shodě | 27 | 3 | `bae9725a098a3bf7…` |
| `06a-nouzova-plna-moc.pdf` | Nouzová omezená provozní plná moc (režim Break-Glass) | 19 | 4 | `a9830c1879766bea…` |
| `06b-protokol-break-glass.pdf` | Protokol o aktivaci a ukončení režimu Break-Glass | 92 | 4 | `93d46e445afc7496…` |
| `07-predzalobni-vyzva.pdf` | Předžalobní výzva k plnění | 43 | 4 | `55ed98d2080b9162…` |
| `08a-smernice-monitoring-komunikace.pdf` | Vnitřní směrnice o monitoringu firemních komunikačních prostředků a nahrávání hovorů | 12 | 5 | `23e757b6ee870513…` |
| `08b-informacni-dolozka-zamestnance.pdf` | Informační doložka o monitoringu firemních komunikačních prostředků a nahrávání hovorů | 14 | 3 | `4897c10ee18ca475…` |
