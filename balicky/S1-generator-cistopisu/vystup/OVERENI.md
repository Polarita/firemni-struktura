# Záznam o ověření generátoru čistopisů (balíček S1 · Verze 3.0)

- **Datum běhu:** 22. 11. 2026 (Linux, `Python 3.14.4`, `markdown 3.11.3`, `pypdf 7.1.1`, headless `Chrome for Testing`)
- **Příkaz:** `python3 generate_pdfs.py` → návratový kód `0`, **`15` dokumentů v `8` sestavách, `69` stran** (`generate_pdfs.py --check` → `VERIFIED_PASS: 15/15`)
- **Testy:** `python3 -m unittest test_generate_pdfs` → všechny testy skončí `OK` (včetně tisku zkušebního PDF, escapování HTML a zneškodnění značek v dosazovaných hodnotách)
- **Co kontrola pokrývá:** úplnost proměnných šablona ↔ data oběma směry, platná hlavička PDF, žádná nevyplněná proměnná v textu PDF, manifest s otisky `SHA-256`; v textu vygenerovaných PDF není žádné číslo předpisu, paragrafu ani označení normy.
- **Co kontrola nepokrývá:** právní a normovou správnost textů. Šablony jsou ukázkové vzory bez odkazů na konkrétní předpisy a normy; závazné znění vznikne v `Bloku 13` převodem právního minima potvrzeného advokátem v `Bloku 8` (nová znění posoudí `15001 pravni-specialista` a potvrdí advokát). Nepokrývá ani běh v zóně `sandbox_airgap`.
- Všechna PDF v této složce nesou vodoznak **VZOR** a obsahují fiktivní data.
- Sloupec „Proměnných“ odpovídá aktuálním šablonám a datům (`generate_pdfs.py --check` → `VERIFIED_PASS: 15/15`). Počty stran a otisky `SHA-256` v tabulce i v manifestech pocházejí z běhu uvedeného výše a po každé změně šablon nebo dat se obnovují novým během generátoru.

| Soubor | Název dokumentu | Proměnných | Stran | SHA-256 PDF |
| :--- | :--- | ---: | ---: | :--- |
| `01-smlouva-o-dilo.pdf` | Smlouva o dílo — elektromontáže, FVE, EV wallboxy a LPS | 46 | 7 | `09cadab1b7fd5b3b…` |
| `01a-zmenovy-list-vicepraci.pdf` | Změnový list víceprací a méněprací | 47 | 3 | `6832b9d04f522de5…` |
| `02-pausalni-servisni-smlouva-mrr.pdf` | Paušální servisní smlouva „Elektro Správa SVJ a Firem“ | 54 | 6 | `109c871c29b1972a…` |
| `03-ramcova-smlouva-certified-partner-sub.pdf` | Rámcová smlouva o spolupráci — Certified Partner SUB | 46 | 6 | `2e91f7f360151489…` |
| `04a-dohoda-odpovednost-sverene-hodnoty-van.pdf` | Dohoda o odpovědnosti k ochraně hodnot svěřených zaměstnanci k vyúčtování — pojízdný sklad | 15 | 3 | `0bcedbee46c4f98e…` |
| `04b-dohoda-svereni-sluzebniho-vozidla.pdf` | Dohoda o svěření služebního vozidla a pravidla jeho užívání | 23 | 5 | `066d8f7ba7ffac75…` |
| `04c-dohoda-sverene-predmety-meridla-oopp.pdf` | Dohoda o odpovědnosti za ztrátu svěřených věcí — měřicí přístroje, OOPP a nářadí | 32 | 3 | `46a8c369c67385f7…` |
| `05a-vyrobni-pas-rozvadece.pdf` | Výrobní pas rozváděče | 95 | 8 | `0fadd2f584b58b33…` |
| `05b-protokol-kusove-zkousky.pdf` | Protokol o kusovém ověření rozváděče | 62 | 4 | `9d7fd6545a9e0934…` |
| `05c-eu-prohlaseni-o-shode.pdf` | EU prohlášení o shodě | 27 | 3 | `63500d5bfb10c1fe…` |
| `06a-nouzova-plna-moc.pdf` | Nouzová omezená provozní plná moc (režim Break-Glass) | 23 | 4 | `e19cd2bd4dffe773…` |
| `06b-protokol-break-glass.pdf` | Protokol o aktivaci a ukončení režimu Break-Glass | 106 | 5 | `252ec8461c591743…` |
| `07-predzalobni-vyzva.pdf` | Předžalobní výzva k plnění | 43 | 4 | `fe5060b17ccc1a4b…` |
| `08a-smernice-monitoring-komunikace.pdf` | Vnitřní směrnice o monitoringu firemních komunikačních prostředků a nahrávání hovorů | 12 | 5 | `db95c8f8a1a9cb66…` |
| `08b-informacni-dolozka-zamestnance.pdf` | Informační doložka o monitoringu firemních komunikačních prostředků a nahrávání hovorů | 14 | 3 | `3a0b2dd638bb6bd7…` |
