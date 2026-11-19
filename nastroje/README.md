# Nástroje návrhu: kanon, kontrola konzistence, jádro promptů a tisková PDF · Polarita s.r.o. (Verze 2.7)

Skripty v této složce udržují návrh vnitřně konzistentní a sestavují tisková PDF. Jsou to nástroje pro práci s dokumentací — nejsou součástí budoucího provozu firmy a nic nenasazují.

## Přehled

| Soubor | K čemu slouží |
| :--- | :--- |
| [`kanon.json`](./kanon.json) | **Jediný zdroj kanonických hodnot:** verze, identifikace firmy, 20 `ai` (číslo, systémové ID, jméno, útvar, měsíční strop), strop `470 USD`, názvy 6 doménových a 9 servisních databází, kanály `Zulip`, síťové zóny, bloky, počty dokumentů a seznam zakázaných (již opravených) výrazů. |
| [`check_consistency.py`](./check_consistency.py) | **Kontrola konzistence:** porovná všechny dokumenty, balíčky i generátory PDF s kanonem a zkontroluje strukturu Markdownu (odkazy, tabulky, bloky kódu, konce řádků). Návratový kód `1` při jakékoli chybě. |
| [`test_check_consistency.py`](./test_check_consistency.py) | Testy kontroly: repozitář musí projít a každé pravidlo musí zachytit podstrčenou vadu. |
| [`sync_prompt_core.py`](./sync_prompt_core.py) | Vloží společné jádro pravidel z [`agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md`](../agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md) jako poslední oddíl systémového promptu všech 20 karet (s číslem, systémovým ID a stropem agenta z kanonu). |
| [`bump_version.py`](./bump_version.py) | Změní číslo verze v kanonu, dokumentech, balíčcích i generátorech PDF. |
| [`pre-commit`](./pre-commit) | Git hook: před commitem, který se dotýká této složky, spustí kontrolu konzistence. |
| [`build_org_pdfs.py`](./build_org_pdfs.py) | Sestaví [`00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.pdf`](../00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.pdf) (A4) a [`01-ORGANIZACNI-MAPA-A3-2026.pdf`](../01-ORGANIZACNI-MAPA-A3-2026.pdf) (A3). |
| [`build_software_pdfs.py`](./build_software_pdfs.py) | Sestaví [`04-KOMPLETNI-SOFTWAROVA-ARCHITEKTURA-POLARITA-2026.pdf`](../04-KOMPLETNI-SOFTWAROVA-ARCHITEKTURA-POLARITA-2026.pdf) (A4, včetně Části III s balíčky `S1–S7`) a [`05-SOFTWAROVA-MAPA-A3-2026.pdf`](../05-SOFTWAROVA-MAPA-A3-2026.pdf) (A3). |

## Běžný postup při úpravě návrhu

```text
1. uprav dokumenty (hodnotu společnou více dokumentům nejprve v kanon.json)
2. python nastroje/sync_prompt_core.py          (jen pokud se měnilo společné jádro promptů)
3. python nastroje/check_consistency.py         (musí skončit s 0 chybami)
4. python nastroje/build_org_pdfs.py  a  python nastroje/build_software_pdfs.py
5. commit — hook pre-commit kontrolu konzistence spustí znovu
```

Změna verze: `python nastroje/bump_version.py <nová verze>`, potom kroky 3 a 4.

Instalace hooku (jednou): z kořene tohoto repozitáře `cp nastroje/pre-commit .git/hooks/pre-commit`. Hook funguje i tehdy, když návrh leží jako podsložka `polarita/firemni-struktura` většího repozitáře: pak se kopíruje do `.git/hooks/` toho repozitáře a u commitů, které se složky netýkají, nedělá nic.

## Co kontrola hlídá

- **Verze:** každá zmínka o verzi musí odpovídat kanonu (výjimkou jsou soubory popisující historii uvedené v `version_allowlist_files`).
- **Agenti:** číslo `ai` nesmí být spojeno s cizím systémovým ID nebo jménem; řádky katalogu v `README.md` a personální tabulky v `00` musí mít správné rozpočty; součet rozpočtů musí dát strop.
- **Bez čísel předpisů a norem:** číslo zákona, vyhlášky nebo nařízení, paragraf, článek předpisu ani označení technické normy nesmí být v žádném dokumentu, balíčku ani generátoru PDF — předpisy a normy se načítají až po nasazení (viz [`06-REGISTR-OVERENI-PRAVA-A-NOREM.md`](../06-REGISTR-OVERENI-PRAVA-A-NOREM.md)).
- **Názvy:** každá databáze `db_*`, každý kanál `#NN-…` a každá síťová zóna musí být v kanonu; počet doménových a servisních databází i jejich výčet musí odpovídat kanonu.
- **Počty dokumentů:** počet souborů na disku musí odpovídat kanonu i číslům uvedeným v `README.md`, v knize `00` a v generátoru PDF.
- **Společné jádro promptů:** znění ve všech 20 kartách musí přesně odpovídat zdroji.
- **Zakázané výrazy:** chyby opravené při auditu (např. chybné označení centrálního skladu, starý název operace ISDS, chybné kódy autorizace ČKAIT, chybná licence knihovny `librosa` — viz registr `06`), zkratka `ai` psaná velkými písmeny v dokumentech jádra, příkazy pro `Docker` a jakékoli odkazy na jiné stroje nebo živý provoz — návrh je čistý koncept pro nový stroj a virtualizace je výhradně `Incus`.
- **Struktura Markdownu:** nefunkční relativní odkazy, tabulky s rozdílným počtem sloupců, neuzavřené bloky kódu, smíšené konce řádků.
- **Upozornění (nezastaví commit):** počet řádků delších než 1 000 znaků v dokumentech jádra.

## Poznámky k tiskovým PDF

- Vyžadují `Python 3.10+`, balík `markdown` (`pip install -r nastroje/requirements.txt`) a nainstalovaný `Chrome` nebo `Edge` (tisk přes headless režim).
- Pomocné HTML předlohy vznikají v dočasné složce systému; výsledná PDF se zapisují do složky návrhu, ale do Gitu se neukládají (jsou v `.gitignore`) — hotová jsou přílohou vydání (Release) příslušné verze. Relativní odkazy se v knihách převádějí na vnitřní kotvy PDF, odkazy mimo knihu se sázejí jako prostý text.
- Texty titulních stran, přehledových tabulek a obou plakátů A3 jsou zapsány přímo ve skriptech. Kontrola konzistence je proto prochází stejně jako dokumenty (verze, zakázané výrazy); věcný obsah plakátů je při změně čísel třeba upravit ručně.
- Skripty běží na Windows i na Linuxu. Běh na Linuxu byl ověřen 15. 11. 2026 na Ubuntu (Python 3.12, Google Chrome): kontrola konzistence, všechny testy, generátor `S1` i sestavení čtyř hlavních PDF prošly. Počty stran se mezi systémy mírně liší podle dostupných písem. Prohlížeč pro tisk lze určit proměnnou `POLARITA_PDF_BROWSER`.
