# Rozvojové balíčky `S1–S7` — rozcestník Etapy II a III · Polarita s.r.o. (Verze 3.14)

Tato složka obsahuje **zapracované rozvojové balíčky `S1–S7`** ze zásobníku [`03-NAVRHY-BALICKU-NA-POZDEJI.md`](../03-NAVRHY-BALICKU-NA-POZDEJI.md). Každá podsložka je samostatný balíček s řídicím dokumentem bloku (`README.md`) ve stejné stavbě jako vrstvy [`software/01–11`](../software/00-SEZNAM-SOFTWARU-README.md): seznam softwaru a modulů, architektonická pravidla, tři realizační prompty, ověřitelné podmínky dokončení a poctivý stav ve Verzi 3.14.

Balíčky navazují na jádro **Etapy I (`Bloky 0–12`)** a nemění ho: počet `ai` zaměstnanců zůstává `20` (`11001`–`18001`), strop `470 USD / měsíc`, `6 + 9` databází `PostgreSQL`, žádné nové oddělení.

## Přehled bloků Etapy II a III

| Blok | Balíček | Složka a řídicí dokument | Co je ve složce | Stav ve Verzi 3.14 |
| :---: | :--- | :--- | :--- | :--- |
| `Blok 13` | **`S1`** Generátor PDF čistopisů smluv a protokolů | [`S1-generator-cistopisu/`](./S1-generator-cistopisu/README.md) | 15 šablon v 8 sestavách, vzorová data, generátor `generate_pdfs.py`, testy, vzorová PDF | Spustitelné a ověřené; čeká převod potvrzeného právního minima do šablon |
| `Blok 14` | **`S2`** Rozšířená regresní sada `Eval Suite 100+` | [`S2-eval-suite/`](./S2-eval-suite/README.md) | 157 scénářů (20 základních + 137 rozšířených), referenční politika, hodnotitel, zvukové makety, testy, trendový report | Spustitelné a ověřené (dry-run `157/157`) |
| `Blok 15` | **`S3`** Konfigurátor balíčků na klíč a kniha tarifů MRR | [`S3-konfigurator-a-tarify/`](./S3-konfigurator-a-tarify/README.md) | `cenik.json`, cenové jádro `pricing.py`, konfigurátor, kniha tarifů, kalkulační a provizní matice, testy | Spustitelné; výchozí ceny schválil `1001` (15. 11. 2026) |
| `Blok 16` | **`S4`** Dílenský terminál rozváděčů a Půjčovna měřidel | [`S4-dilensky-terminal-a-pujcovna/`](./S4-dilensky-terminal-a-pujcovna/README.md) | Specifikace, 2 schémata pro `metadata-schema-kernel`, checklist kusového ověření, předávací protokol | Specifikace připravená k vývoji |
| `Blok 17` | **`S5`** Dvoustranný elektronický podpis a noční hlasová `ai` recepční | [`S5-podpis-a-hlasova-recepcni/`](./S5-podpis-a-hlasova-recepcni/README.md) | Specifikace, podpisový workflow, scénář hlasové recepční, příklad konfigurace | Specifikace připravená k vývoji |
| `Blok 18` | **`S6`** Samo-dokumentující E2E testy a 30min vývojová smyčka UI | [`S6-ziva-prirucka-e2e/`](./S6-ziva-prirucka-e2e/README.md) | Specifikace, pravidla fronty, vzorový test `Playwright` a sdílená pomocná funkce kroku | Specifikace připravená k vývoji |
| `Blok 19` | **`S7`** Polarita Elektro Cloud (`N9`, Strategická Etapa III) | [`S7-polarita-elektro-cloud/`](./S7-polarita-elektro-cloud/README.md) | Specifikace, brána `Go / No-Go`, vzor `Row-Level Security`, struktura tarifů, osnova licenčních podmínek | Architektura připravena; spuštění podmíněno bránou |

## Pravidla aktivace

1. **Až po ostrém startu.** Žádný z bloků `13–19` se nespouští před `12/12 PASS` přejímací brány `Go-Live Gate` (`Blok 12`). Etapa I nevyžaduje spuštění žádného z těchto bloků; `Blok 7` pouze čte ze složky `S2-eval-suite/` dva hotové soubory (základní sadu `ES-001`–`ES-020` v `eval_suite_polarita_extended.json` a `reference_policy.py`).
2. **Samostatně a v libovolném pořadí.** Bloky `13–18` lze spouštět v libovolném pořadí (doporučené pořadí je `13 → 18`) s jedinou vazbou: přejímka `Bloku 17` používá hodnotitel a scénáře balíčku `S2` (`Blok 14`). `Blok 15` na smluvní šablonu č. 2 balíčku `S1` jen odkazuje; jeho `DoD` na `Bloku 13` nezávisí.
3. **`Blok 19` má vlastní bránu.** Polarita Elektro Cloud se spustí až po splnění a podpisu brány `Go / No-Go` (12–18 měsíců provozu, 100+ objektů, 500+ dokumentů, 100 % `Eval Suite`, 15+ partnerů).
4. **Co je „hotovo“.** Ve Verzi 3.14 jsou balíčky `S1–S3` spustitelné přímo z této složky a ověřené spuštěním; `S4–S7` jsou úplné specifikace s realizačními prompty. V testovacím ředitelství na VM `polarita-hq` je dostupný konfigurátor S3. Protokoly z ostatních zkoušek jsou ve VM pod `/srv/polarita/workspace/dukazy/`.

## Automatická kontrola

Soubor [`ci-gitea-actions-priklad.yml`](./ci-gitea-actions-priklad.yml) je vzor úlohy pro `Gitea Actions` (runner v režimu `host` uvnitř kontejneru `Incus`, bez Dockeru), která spouští kontrolu konzistence návrhu a testy balíčků `S1–S3`. Vzor nebyl spuštěn na živém runneru `Gitea` (`Gitea` vzniká až v `Bloku 5`); kontroly a testy byly ověřeny lokálně na Windows a jednorázově dne 15. 11. 2026 na Ubuntu (živé `Gitea Actions` zůstává neověřené).

## Rychlé spuštění spustitelných balíčků

```text
cd S1-generator-cistopisu   &&  pip install -r requirements.txt  &&  python generate_pdfs.py
cd S2-eval-suite            &&  python -m unittest test_eval_suite  &&  python run_eval_suite.py
cd S3-konfigurator-a-tarify &&  python -m unittest test_pricing     &&  python pricing.py --build
```
