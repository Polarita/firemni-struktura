# Blok 13 · Balíček S1 — Automatizovaný generátor PDF čistopisů smluv a protokolů · Verze 3.30

Tento dokument je řídicím dokumentem **`Bloku 13`** Rozvojové Etapy II společnosti **Polarita s.r.o.** Balíček povyšuje právní a provozní minimum potvrzené advokátem po převzetí systému na **šablonovaný generátor tiskových PDF čistopisů**: 15 šablon v 8 sestavách s jednotnými proměnnými, vzorová data, generátor [`generate_pdfs.py`](./generate_pdfs.py) a manifest každého dokumentu pro transakční diff `mutation_confirm`. Šablony vyplňují agenti `15001 pravni-specialista`, `14005 zakazky`, `13001 eshop`, `16002 tajemnik` a `18001 personalista`. Balíček nepřidává žádného `ai` agenta ani databázi.

> **Právní upozornění:** Šablony jsou ukázkové pracovní vzory připravené `ai` bez odkazů na konkrétní právní předpisy a normy. Závazné znění do nich vzniká v `Bloku 13` převodem právního minima, které po převzetí připraví `1001` s advokátem a advokát potvrdí; nová znění, která v potvrzeném minimu nejsou, posoudí `15001 pravni-specialista` a před prvním ostrým použitím potvrdí **advokát** (technické sestavy `15002 normovac`). Podpis je vždy úkon člověka (`1001`, u revizí RT). Hodnoty, které návrh firmy nestanoví (smluvní pokuty, záruky, výše paušálu), jsou proměnné, ne pevná čísla.

---

## 1. Seznam softwaru a modulů

| Oblast | Soubor / modul | Kanál / Režim | Role a použití v Polarita s.r.o. (Verze 3.30) | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Šablony** | [`sablony/`](./sablony/) (15× `.md`) | verzováno v `Gitea`, cílově `/srv/polarita/vault/04-Pravo-a-Smlouvy/` | Čistopisy v Markdownu s proměnnými `{{snake_case}}`; první řádek nadpis, druhý řádek `**Spis:** {{spis_id}}`. | `15001` `pravni-specialista` *(technické sestavy `15002` `normovac`)* |
| **Vzorová data** | [`data/`](./data/) (15× `.json`) | fiktivní hodnoty | Ke každé šabloně plochý JSON se všemi proměnnými — slouží k testu a jako vzor vstupu. Žádné skutečné osobní údaje. | `15001` `pravni-specialista` |
| **Generátor** | [`generate_pdfs.py`](./generate_pdfs.py) | `Python` + `markdown` + headless `Chrome / Edge / Chromium` | Vyplní šablonu, vysází A4 a vytiskne PDF bez přístupu k síti; kontroluje úplnost proměnných oběma směry; zapíše manifest (proměnné + `SHA-256` šablony, dat a PDF). | `17001` `programator` *(kontrola `17004` `klicnik`)* |
| **Testy** | [`test_generate_pdfs.py`](./test_generate_pdfs.py) | `python -m unittest` | Vyplňování, chybové stavy, shoda šablon s daty a tisk zkušebního PDF. | `17004` `klicnik` |
| **Výstupy** | [`vystup/`](./vystup/) | generováno | Manifesty a záznam z ověřovacího běhu; vzorová PDF s vodoznakem `VZOR` vzniknou spuštěním generátoru, do Gitu se neukládají a hotová jsou přílohou vydání (Release) příslušné verze. | — |
| **Podpis a archiv** | `JSignPdf` (`QES` na čipu `QSCD`), `pyHanko`, `legal-archive` | z `Bloku 4` a `Bloku 5` | Smlouvy podepisuje `1001` osobním `QES`; interní záznamy pečetí `pyHanko`; podepsané PDF jde do `legal-archive`. Dvoustranný elektronický podpis přidává balíček `S5`. | `1001`, `17004` `klicnik` |

---

## 2. Architektonická pravidla a zdůvodnění

1. **Osm sestav balíčku `S1`:**

   | Č. | Sestava | Šablony |
   | :---: | :--- | :--- |
   | 1 | Smlouva o dílo (elektromontáže / FVE / EV wallboxy / LPS) + Změnový list víceprací | `01-smlouva-o-dilo`, `01a-zmenovy-list-vicepraci` |
   | 2 | Paušální servisní smlouva „Elektro Správa SVJ a Firem“ (MRR) | `02-pausalni-servisni-smlouva-mrr` |
   | 3 | Rámcová B2B a partnerská smlouva `Certified Partner SUB` (`N8`) | `03-ramcova-smlouva-certified-partner-sub` |
   | 4 | Dohody o odpovědnosti: svěřené hodnoty `VAN-*` (dohoda o odpovědnosti za schodek na svěřených hodnotách k vyúčtování), služební vozidlo (obecná odpovědnost za škodu), měřidla / OOPP / nářadí (dohoda o odpovědnosti za ztrátu svěřených věcí) | `04a-…-sverene-hodnoty-van`, `04b-…-sluzebniho-vozidla`, `04c-…-meridla-oopp` |
   | 5 | Výrobní pas rozváděče, protokol o kusovém ověření a EU prohlášení o shodě (CE) | `05a-vyrobni-pas-rozvadece`, `05b-protokol-kusove-zkousky`, `05c-eu-prohlaseni-o-shode` |
   | 6 | Nouzová plná moc a protokol `Break-Glass` (`SUB-1007`) | `06a-nouzova-plna-moc`, `06b-protokol-break-glass` |
   | 7 | Předžalobní výzva | `07-predzalobni-vyzva` |
   | 8 | Směrnice a informační doložka o monitoringu komunikace a nahrávání hovorů (`K5`) | `08a-smernice-monitoring-komunikace`, `08b-informacni-dolozka-zamestnance` |

2. **Jednotné proměnné:**
   * Společné názvy napříč šablonami: `{{spis_id}}`, `{{ico_klienta}}`, `{{castka_bez_dph}}`, dále `{{nazev_klienta}}`, `{{sidlo_klienta}}`, `{{datum_podpisu}}`, `{{pracovni_pozice}}` a další. Generátor selže, pokud kterákoli proměnná chybí, přebývá nebo je prázdná.
   * Tabulky s pevným počtem řádků ve vzorových šablonách (`01a`, `04c`, `05a`, `05b`, `06b`) slouží jako pevný demonstrátor struktury; před ostrým nasazením v `Bloku 13` se pro zakázky s proměnným počtem položek rozšíří o generované opakovatelné bloky řádků nad polem vstupních dat.
   * Osobní údaje zaměstnanců se do pracovních konceptů nedostávají — dohody pracují s osobním číslem (`1001+`) a jménem (u finálního podpisového originálu plné moci `06a` se doplňují identifikační údaje zmocněnce); rodná čísla a adresy zůstávají v `db_hr_lide`.
3. **`ai` připravuje, člověk podepisuje:**
   * Výchozí běh tiskne vodoznak `VZOR` i evidenční patičku konceptu. Přepínač `--final` (bez vodoznaku a bez interní ai patičky) se používá až po kontrole `15001` a schválení v `Decisions`.
   * Generátor nikdy nepodepisuje ani neodesílá. EU prohlášení o shodě a revizní dokumenty podepisuje výhradně oprávněná fyzická osoba.
4. **Sazba `Typst` × `HTML → PDF`:**
   * Zadání připouští obě cesty. Tento balíček používá `HTML → PDF` (headless Chromium, tisk bez sítě), protože běží bez instalace dalšího sázecího nástroje. Na `polarita-hq` poběží tisk v bez-síťové zóně `sandbox_airgap`; přechod na `Typst` je možný beze změny šablon a dat.

---

## 3. Pokyny k instalaci a konfiguraci pro `ai` (Prompty)

### Prompt 1 — Převod potvrzeného právního minima do šablon a jejich kontrola (`pro 15001 pravni-specialista` + `15002 normovac`)

```text
Zkontroluj převod právního minima potvrzeného advokátem po převzetí systému do šablon balíčku S1 společnosti Polarita s.r.o. před prvním ostrým použitím. Šablony sám nepíšeš ani neměníš; tvé nálezy a každé nové znění, které v potvrzeném minimu není, potvrzuje advokát:

1. Přečti všech 15 šablon ve složce balicky/S1-generator-cistopisu/sablony a ověř každý věcný odkaz na právní předpisy a normy proti aktuálnímu znění v právní a normové bázi ve Vaultu (občanské právo, pracovněprávní předpisy, předpisy o bezpečnosti provozu vyhrazených technických zařízení, o odborné způsobilosti v elektrotechnice a o posuzování shody elektrických zařízení nízkého napětí, předžalobní výzva, GDPR, předpisy EU o umělé inteligenci; normy v 03-Normy-a-Metodiky/).
2. U každé šablony porovnej text s potvrzeným právním minimem a sepiš nález: odchylka od potvrzeného znění, věcná chyba, chybějící ustanovení, riziko pro Polaritu, doporučená úprava. Nic v šablonách sám neměň.
3. Technické sestavy č. 5 (pas rozváděče, kusové ověření, prohlášení o shodě) posoudí 15002 normovac proti platné normě pro rozváděče nízkého napětí a příslušné výrobkové normě.
4. Výsledek předej jako verdikt VERIFIED_PASS / REJECTED do Decisions a označ šablony, které musí před použitím vidět advokát.
```

### Prompt 2 — Nasazení generátoru na `polarita-hq` (`pro 17001 programator` + `17004 klicnik`)

```text
Nasaď generátor PDF čistopisů na server polarita-hq:

1. Ulož šablony do /srv/polarita/vault/04-Pravo-a-Smlouvy/sablony/ (neosobní vzory, 0 PII) a generátor do Gitea; spusť python -m unittest test_generate_pdfs a python generate_pdfs.py — pokračuj jen při úspěchu všech dokumentů.
2. Tisk PDF spouštěj v bez-síťovém kontejneru zóny sandbox_airgap (eth0 none); vstupní data předávej jako JSON soubor, výstup jako PDF + manifest.
3. Zaregistruj typovaný MCP nástroj generate_document(template, data), který ai agentům vrací pouze cestu ke konceptu s vodoznakem VZOR a manifest; běh bez vodoznaku (--final) povol jen po mutation_confirm v Decisions.
4. Po podpisu (QES 1001 v JSignPdf, případně pečeť pyHanko u interních záznamů) ulož dokument do legal-archive a otisk SHA-256 zapiš do spisu POL-RRRR-NNNNN.
5. Předej nasazení ke kontrole 17004 klicnik (žádná tajemství v šablonách ani datech, žádná síť při tisku).
```

### Prompt 3 — Vyplnění dokumentu ke spisu (`pro 14005 zakazky`, `13001 eshop`, `16002 tajemnik` a `18001 personalista`)

```text
Připrav koncept dokumentu ke konkrétnímu spisu:

1. Zvol šablonu podle sestavy (1–8) a načti hodnoty proměnných výhradně ze spisu POL-RRRR-NNNNN, z cz-sk-registry-kernel (IČO, DIČ, sídlo) a ze schváleného ceníku; nic nedomýšlej — chybějící údaj vrať jako dotaz.
2. Osobní údaje zaměstnanců ber jen přes Clean Room (jméno a osobní číslo); rodná čísla ani adresy do dokumentu nevkládej.
3. Zavolej generate_document; zkontroluj manifest a koncept s vodoznakem VZOR předej 15001 pravni-specialista.
4. Po VERIFIED_PASS předlož jednateli 1001 do Decisions diff proměnných před → po a teprve po mutation_confirm vygeneruj čistopis k podpisu.
5. Dokument nikdy sám nepodepisuj ani neodesílej.
```

---

## 4. Ověřitelné podmínky dokončení Bloku 13

- [ ] `python generate_pdfs.py` vrátí kód `0` a všech 8 sestav (15 šablon) vytvoří platné PDF bez nevyplněné proměnné.
- [ ] Proměnné `{{spis_id}}`, `{{ico_klienta}}` a `{{castka_bez_dph}}` jsou v šablonách použity jednotně a každý dokument má manifest pro diff `mutation_confirm`.
- [ ] Do šablon je převedeno právní minimum potvrzené advokátem po převzetí systému; převod zkontroloval `15001` (právo) a `15002` (sestava č. 5), nová znění potvrdil advokát, nálezy jsou zapracovány a šablony odpovídají dokumentu `00-KOMPLETNI-NAVRH-FIRMY-POLARITA-2026.md`.
- [ ] Tisk na `polarita-hq` běží v `sandbox_airgap` bez sítě a běh `--final` je možný jen po `mutation_confirm`.
- [ ] Podepsaný dokument je v `legal-archive` a jeho otisk ve spisu `POL-RRRR-NNNNN`.

---

## 5. Stav ve Verzi 3.30

Balíček je spustitelný a ověřený spuštěním; čeká převod potvrzeného právního minima do šablon. Stav ověřovacího běhu (počet vygenerovaných PDF, počet stran, výsledky testů) je zapsán v souboru [`vystup/OVERENI.md`](./vystup/OVERENI.md).

**Vyžaduje rozhodnutí, odbornou revizi nebo živý server:**

- převod právního minima potvrzeného advokátem po převzetí systému do šablon (nová znění posoudí `15001` a potvrdí advokát) a normová revize sestavy č. 5 (`15002`) — do té doby jde o pracovní vzory;
- nasazení generátoru do `sandbox_airgap`, MCP nástroj `generate_document` a napojení na `Decisions` a `legal-archive`.

Spuštění: `pip install -r requirements.txt` · `python generate_pdfs.py --check` · `python generate_pdfs.py` · `python -m unittest -v test_generate_pdfs`.
