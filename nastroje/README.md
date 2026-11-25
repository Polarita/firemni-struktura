# Nástroje návrhu: kanon, kontrola konzistence, jádro promptů a tisková PDF · Polarita s.r.o. (Verze 3.26)

Skripty v této složce udržují návrh vnitřně konzistentní a sestavují tisková PDF. Jsou to nástroje pro práci s dokumentací — nejsou součástí budoucího provozu firmy a nic nenasazují.

## Přehled

| Soubor | K čemu slouží |
| :--- | :--- |
| [`kanon.json`](./kanon.json) | **Jediný zdroj kanonických hodnot:** verze, identifikace firmy, 20 `ai` (číslo, systémové ID, jméno, útvar, měsíční strop), strop `470 USD`, názvy 6 doménových a 9 servisních databází, kanály `Zulip`, síťové zóny, bloky, počty dokumentů a seznam zakázaných (již opravených) výrazů. |
| [`check_consistency.py`](./check_consistency.py) | **Kontrola konzistence:** porovná s kanonem každý textový soubor, který `Git` sleduje nebo by sledoval (dokumenty, balíčky, skripty, konfigurace i soubory bez přípony), a zkontroluje strukturu Markdownu (odkazy, kotvy, tabulky, bloky kódu, konce řádků). Mimo pracovní kopii `Gitu` projde celý strom složky. Návratový kód `1` při jakékoli chybě, `2` při neznámém přepínači; přepínač `--warnings` vypíše i upozornění. |
| [`test_check_consistency.py`](./test_check_consistency.py) | Testy kontroly: repozitář musí projít, každé pravidlo (včetně každého zakázaného vzoru kanonu) musí zachytit podstrčenou vadu a legitimní text nesmí označit. Celý program se navíc spouští nad dočasnou kopií složky s podstrčenými vadami a ověřuje se návratový kód; do složky samotné testy nic nezapisují. |
| [`sync_prompt_core.py`](./sync_prompt_core.py) | Vloží společné jádro pravidel z [`agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md`](../agenti-a-prompty/00-SPOLECNE-JADRO-PROMPTU.md) jako poslední oddíl systémového promptu všech 20 karet (s číslem, systémovým ID a stropem agenta z kanonu). Agentům, o nichž jádro mluví ve třetí osobě (`11001`, `14005`, `15001`, `15002`, `17004`, `17005`), upraví větu, podle které by jinak eskalovali sami sobě nebo žádali sami sebe; do úvodního řádku jádra dopočítá z kanonu provozní kvótu agenta (85 % jmenovitého podílu); chybí-li ve zdroji přesné znění takové věty, skončí chybou a nic nezapíše. Přepínač `--check` jen porovná a nic nemění. |
| [`bump_version.py`](./bump_version.py) | Změní číslo verze v kanonu a ve všech souborech, které kontrola čte — ve všech tvarech zápisu, které kontrola rozpozná. Přijme jen tvar `hlavní.vedlejší` bez úvodních nul a po přepsání sama spustí kontrolu konzistence. |
| [`pre-commit`](./pre-commit) | Git hook: před commitem, který se dotýká této složky, spustí nad stavem připraveným ke commitu (export indexu do dočasné složky, ne pracovní strom) kontrolu konzistence a její testy, kontrolu šablon `S1`, dry-run sady `S2` a testy cenového jádra `S3`. |
| [`build_org_pdfs.py`](./build_org_pdfs.py) | Sestaví [`00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.pdf`](https://github.com/Polarita/firemni-struktura/releases/download/Polarita-3.26/00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.pdf) (A4) a [`01-ORGANIZACNI-MAPA-A3-2026.pdf`](https://github.com/Polarita/firemni-struktura/releases/download/Polarita-3.26/01-ORGANIZACNI-MAPA-A3-2026.pdf) (A3). |
| [`build_software_pdfs.py`](./build_software_pdfs.py) | Sestaví [`04-KOMPLETNI-SOFTWAROVA-ARCHITEKTURA-POLARITA-2026.pdf`](https://github.com/Polarita/firemni-struktura/releases/download/Polarita-3.26/04-KOMPLETNI-SOFTWAROVA-ARCHITEKTURA-POLARITA-2026.pdf) (A4, včetně Části III s balíčky `S1–S7`) a [`05-SOFTWAROVA-MAPA-A3-2026.pdf`](https://github.com/Polarita/firemni-struktura/releases/download/Polarita-3.26/05-SOFTWAROVA-MAPA-A3-2026.pdf) (A3). |

## Instalace

Nástroje i balíčky `S1–S3` vyžadují `Python 3.10` nebo novější. Kontrola konzistence, synchronizace jádra promptů, sada `S2` a cenové jádro `S3` používají jen standardní knihovnu; závislosti potřebují pouze generátory PDF:

```text
python -m venv .venv                      (doporučeno; složka .venv je v .gitignore)
.venv/bin/pip install -r nastroje/requirements.txt                          (sestavení knih a plakátů: markdown)
.venv/bin/pip install -r balicky/S1-generator-cistopisu/requirements.txt    (čistopisy S1: markdown, pypdf)
```

Na Windows je cesta k nástroji `pip` ve virtuálním prostředí `.venv\Scripts\pip`. Tisk PDF navíc potřebuje prohlížeč `Chrome`, `Edge` nebo `Chromium`; jeho cestu lze určit proměnnou `POLARITA_PDF_BROWSER`.

Ověření instalace — každý řádek se spouští z kořene repozitáře, závorky vracejí adresář zpět (vše musí skončit `OK`, sada `S2` výsledkem `VERIFIED_PASS`):

```text
(cd nastroje                          && ../.venv/bin/python -m unittest test_check_consistency)
(cd balicky/S1-generator-cistopisu    && ../../.venv/bin/python generate_pdfs.py --check && ../../.venv/bin/python -m unittest test_generate_pdfs)
(cd balicky/S2-eval-suite             && ../../.venv/bin/python -m unittest test_eval_suite && ../../.venv/bin/python run_eval_suite.py --no-history)
(cd balicky/S3-konfigurator-a-tarify  && ../../.venv/bin/python pricing.py --build && ../../.venv/bin/python -m unittest test_pricing)
```

Bez prohlížeče se tiskové testy `S1` a test javascriptového jádra konfigurátoru `S3` přeskočí; s proměnnou `POLARITA_REQUIRE_BROWSER=1` (takto běží CI) je chybějící prohlížeč selháním. Běžné běhy nezanechávají v pracovním stromu žádné nové soubory, které by `Git` viděl: reporty sady `S2` jdou do ignorované složky `output/behy/` (nebo do `--out-dir`), zvukové makety a tisková PDF jsou v `.gitignore`.

## Běžný postup při úpravě návrhu

```text
1. uprav dokumenty (hodnotu společnou více dokumentům nejprve v kanon.json)
2. python nastroje/sync_prompt_core.py          (jen pokud se měnilo společné jádro promptů)
   python nastroje/sync_prompt_core.py --check  (jen porovná, nic nemění)
3. python nastroje/check_consistency.py         (musí skončit s 0 chybami)
4. python nastroje/build_org_pdfs.py  a  python nastroje/build_software_pdfs.py
5. commit — hook pre-commit spustí kontrolu znovu nad stavem připraveným ke commitu
```

Změna verze: `python nastroje/bump_version.py <nová verze>` (kontrolu z kroku 3 spustí skript sám), potom krok 4 a nové sestavení čistopisů `S1`.

Instalace hooku (jednou): z kořene tohoto repozitáře `cp nastroje/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`. Hook funguje i tehdy, když návrh leží jako podsložka `Polarita/firemni-struktura` (příp. `polarita/firemni-struktura`) většího repozitáře: pak se kopíruje do `.git/hooks/` toho repozitáře a u commitů, které se složky netýkají, nedělá nic. Hook kontroluje přesně to, co se commituje: připravenou (`git add`) vadu nezakryje oprava, která zatím zůstala jen v pracovním stromu, a naopak rozpracované změny commit neblokují. Po sobě nenechává žádné soubory.

## Co kontrola hlídá

- **Rozsah:** pravidla kanonu platí pro každý textový soubor bez ohledu na příponu; struktura Markdownu se kontroluje v souborech `.md`. Nezlomitelná mezera se před porovnáním bere jako obyčejná, takže zakázaný výraz ani cizí verzi neschová typografie. Soubor, který není platné `UTF-8`, je chyba.
- **Verze:** každá zmínka o verzi (`Verze`, `verzi`, `verzí`, `Version`, i s formátováním Markdownu, a značka `Polarita-…`) v dokumentech, skriptech i konfiguračních a kódových souborech balíčků musí odpovídat kanonu (výjimkou jsou soubory popisující historii uvedené v `version_allowlist_files`).
- **Agenti:** číslo `ai` nesmí být spojeno s cizím systémovým ID nebo jménem (v obou pořadích a s běžnými oddělovači); řádky katalogu v `README.md`, personální tabulky v `00`, nadpisy karet i ručně psané nadpisy agentů v generátoru PDF musí odpovídat kanonu; součet rozpočtů musí dát strop.
- **Identifikace firmy a strop:** IČO, DIČ a ID datové schránky společnosti i celofiremní strop v USD musí odpovídat kanonu (vzorové smlouvy `S1` s fiktivními protistranami jsou z kontroly IČO a DIČ vyňaty).
- **Bez čísel předpisů a norem:** číslo zákona, vyhlášky nebo nařízení, paragraf, článek předpisu ani označení technické normy nesmí být v žádném dokumentu, balíčku ani generátoru PDF — předpisy a normy se načítají až po nasazení (viz [`06-REGISTR-OVERENI-PRAVA-A-NOREM.md`](../06-REGISTR-OVERENI-PRAVA-A-NOREM.md)).
- **Názvy:** každá databáze `db_*`, každý kanál `#NN-…` a každá síťová zóna musí být v kanonu; počet doménových a servisních databází i jejich výčet musí odpovídat kanonu.
- **Počty dokumentů:** počet souborů na disku musí odpovídat kanonu i číslům uvedeným v `README.md`, v knize `00` a v generátoru PDF.
- **Společné jádro promptů:** znění ve všech 20 kartách musí přesně odpovídat zdroji (včetně personalizovaných vět pro `11001`, `14005`, `15001`, `15002`, `17004`, `17005` a dopočtené provozní kvóty).
- **Zakázané výrazy:** chyby opravené při auditu (např. chybné označení centrálního skladu, starý název operace ISDS, chybné kódy autorizace ČKAIT, chybná licence knihovny `librosa` — viz registr `06`), zkratka `ai` psaná velkými písmeny v celém repozitáři (mimo `GS1 AI` a `SCREAMING_SNAKE_CASE` konstant v kódu), únik osobních údajů jednatele, příkazy pro `Docker` a jakékoli odkazy na jiné stroje nebo živý provoz — návrh je čistý koncept pro nový stroj a virtualizace je výhradně `Incus`.
- **Struktura Markdownu:** nefunkční relativní odkazy (včetně odkazů s titulkem, referenčních odkazů a atributů `href` / `src`; rozhoduje přesná velikost písmen cesty), nefunkční kotvy nadpisů, odkazy na PDF, které žádný generátor nevytváří, tabulky s rozdílným počtem sloupců (i bez úvodního svislítka), neuzavřené bloky kódu obou druhů, smíšené konce řádků.
- **Upozornění (nezastaví commit):** počet řádků delších než 1 000 znaků v dokumentech jádra.

## Poznámky k tiskovým PDF

- Vyžadují `Python 3.10+`, balík `markdown` (`pip install -r nastroje/requirements.txt`) a nainstalovaný `Chrome`, `Edge` nebo `Chromium` (tisk přes headless režim).
- Pomocné HTML předlohy vznikají v dočasné složce systému; výsledná PDF se zapisují do složky návrhu, ale do Gitu se neukládají (jsou v `.gitignore`) — hotová jsou přílohou vydání (Release) příslušné verze. Relativní odkazy se v knihách převádějí na vnitřní kotvy PDF, odkazy mimo knihu se sázejí jako prostý text.
- Texty titulních stran, přehledových tabulek a obou plakátů A3 jsou zapsány přímo ve skriptech. Kontrola konzistence je proto prochází stejně jako dokumenty (verze, zakázané výrazy); věcný obsah plakátů je při změně čísel třeba upravit ručně.
- Skripty běží na Windows i na Linuxu. Běh na Linuxu byl ověřen 15. 11. 2026 na Ubuntu (Python 3.12, Google Chrome): kontrola konzistence, všechny testy, generátor `S1` i sestavení čtyř hlavních PDF prošly. Počty stran se mezi systémy mírně liší podle dostupných písem. Prohlížeč pro tisk lze určit proměnnou `POLARITA_PDF_BROWSER`.
