# Fronta 30min vývojové smyčky UI — pravidla · Blok 18 (S6) · Verze 3.2.2

Tento dokument stanoví pravidla fronty drobných interních úprav ne-normového UI a tiskových sestav nad **`metadata-schema-kernel`**. Doplňuje řídicí dokument [`README.md`](README.md) (kapitola 2, pravidla 5–7). Smyčka je připravený návrh — na živém serveru zatím nebyla spuštěna (server `polarita-hq` neexistuje).

---

## 1. Účel a role

- **Účel:** rychle a bezpečně vyřídit malou úpravu formuláře nebo interní tiskové sestavy tak, aby `1001` dostal do **`Decisions`** hotový náhled se screenshoty **`před → po`** a rozhodl jedním úkonem (`mutation_confirm` / `mutation_cancel`).
- **Třídění a měření času:** `17005 ai-provoz`.
- **Worker:** `17001 programator` v odděleném klonu **`wt-worker`**.
- **Judge:** **`AigisCode`** (deterministická kontrola) + `17004 klicnik` ve **`wt-judge`**, na modelu jiného výrobce než Worker. `wt-worker` a `wt-judge` jsou dva oddělené klony repozitáře (každý s vlastním `.git`), ne sdílené worktree; `Judge` tak nevidí rozpracované soubory ani historii příkazů tvůrce.
- **Rozhodnutí:** `1001` v `Decisions`. Bez `mutation_confirm` se nic neslučuje do hlavní větve.
- **Umístění fronty:** požadavky jako úkoly v `Gitea` se štítkem `ui-30min`, přidělování přes `Paperclip` — `NÁVRH — ke schválení 1001`.

---

## 2. Co do fronty smí

Pouze změny prezentační vrstvy vlastních modulů Polarity nad `metadata-schema-kernel`, které nemění uložená data, výpočty ani oprávnění:

- popisky polí, nápovědy, zástupné texty a chybové hlášky formuláře,
- pořadí, seskupení a šířka polí, rozložení formuláře na počítači a v mobilu,
- viditelnost už existujícího pole ve formuláři nebo sloupce v přehledu (bez změny oprávnění k datům),
- vzhled a rozložení **interní** tiskové sestavy bez normového a právně závazného obsahu (např. interní přehled, pracovní lístek, skladová výdejka): záhlaví, pořadí sloupců, písmo, okraje, logo,
- oprava překlepu nebo sjednocení terminologie v UI.

Podmínkou je, že dotčený proces má E2E test z Bloku 18 (jinak nelze pořídit snímky `před → po` ani změnu ověřit).

**Povolené cesty.** Diff smí zasáhnout jen do cest z tohoto výčtu; cokoli jiného `AigisCode` v kroku 4 odmítne. Výčet je `NÁVRH — ke schválení 1001`: skutečné názvy složek určí `17001` podle struktury vlastních modulů při stavbě Bloku 18, zapíší se do pravidel `AigisCode` (která mění jen `1001` / `17004`) a tato tabulka se s nimi musí shodovat.

| Povolená cesta (vzor uvnitř vlastního modulu nad `metadata-schema-kernel`) | Co v ní smyčka smí |
| :--- | :--- |
| `<modul>/ui/forms/**` | Rozložení, pořadí, seskupení a šířka polí formuláře; viditelnost existujícího pole. |
| `<modul>/ui/lists/**` | Viditelnost a pořadí existujících sloupců přehledu. |
| `<modul>/ui/i18n/cs/**` | Popisky, nápovědy, zástupné texty a chybové hlášky. |
| `<modul>/print/internal/**` | Šablony interních tiskových sestav bez normového a právně závazného obsahu. |
| `e2e/<proces>.spec.ts` | Pouze přidání nového popsaného kroku nebo ověření; nic se nemaže ani neoslabuje. |

Mimo výčet zůstává vždy: deklarativní schémata entit (`schemata/**`), migrace, kód výpočtů a validací, sdílená pomocná funkce `krok.ts`, konfigurace CI a vše z kapitoly 3.

---

## 3. Co do fronty nesmí

Požadavek, který se dotýká kterékoliv položky níže, třídění odmítne a vrátí do běžného vývojového postupu (`Worker / Judge` z `Bloku 7` bez časového boxu, s příslušným odborným `Judge`):

- **normové jádro ČSN `cad-urs-engine`** — vzorce, výpočty, registr norem, texty a šablony Výrobního pasu rozváděče, revizní zprávy, protokolů a prohlášení o shodě,
- **`Hard-Stop` zámky `db_hr_lide`** a cokoliv v `db_hr_lide` / `db_gdpr_zkousky`, včetně pohledů `Clean Room`,
- jakákoliv změna, která by vygenerovala migraci databáze (nové pole, změna typu, nová entita, změna validace ukládaných dat),
- vendor schémata a kód cizích aplikací (`Keycloak`, `Gitea`, `Zulip`, `Stalwart Mail`, `Chatwoot CE`, `Moodle`, `MedusaJS`, `Paperless-ngx`, `Vikunja`, `Umami`, `Traccar`),
- autorizace, role, ACL nástrojů, tajemství a vše kolem `OpenBao`, `Keycloak` a podpisů (`pyHanko`, `JSignPdf`),
- `comm-gateway`, `isds-podatelna-bridge`, `finance-uol-marze-engine`, `cz-sk-registry-kernel` a `Hard-Stop` zámek `DTM ČR`,
- tiskové sestavy s právně nebo normově závazným obsahem (daňové doklady, smlouvy, Elektronický stavební deník, revizní zprávy, pasy, pracovněprávní dokumenty),
- prompty a karty `ai` pozic, `Eval Suite`, pravidla `AigisCode`, pipeline `Gitea Actions` a samotná pravidla této fronty,
- změna E2E testu, která by oslabila kontrolu (smazání kroku nebo ověření) — test se smí pouze doplnit o nový popsaný krok.

---

## 4. Vstupní šablona požadavku

```yaml
# Požadavek do fronty 30min smyčky UI (vyplňuje zadavatel; jedna úprava = jeden požadavek)
zadavatel: ""            # číslo ai zaměstnance nebo fyzické osoby, např. 14005 nebo 1001
utvar: ""                # 11–18
typ: ""                  # formular | tiskova-sestava
modul: ""                # vlastní modul nad metadata-schema-kernel, např. centralni-lhutnik-a-objekty
obrazovka_nebo_sestava: ""   # název formuláře / sestavy, jak je vidět v UI
soucasny_stav: ""        # co uživatel vidí dnes (1–2 věty)
pozadovany_stav: ""      # co má vidět po úpravě (1–2 věty, ověřitelně)
duvod: ""                # proč (komu to pomůže)
e2e_test: ""             # soubor testu z Bloku 18, který obrazovku pokrývá
potvrzeni_zadavatele:
  nemeni_ulozena_data: true      # žádná migrace DB
  nemeni_vypocty_ani_normy: true # nedotýká se cad-urs-engine
  nemeni_opravneni: true         # nedotýká se rolí, ACL, Clean Room, db_hr_lide
```

Požadavek s nevyplněným polem, s více úpravami najednou nebo s kterýmkoliv potvrzením `false` se do smyčky nepřijme.

---

## 5. Průběh: Worker → Judge → Decisions

| Krok | Kdo | Co udělá | Výstup |
| :--- | :--- | :--- | :--- |
| 0. Třídění | `17005` `ai-provoz` | Zkontroluje šablonu, kapitoly 2 a 3 a existenci E2E testu; spustí časový box 30 minut. | Přijato / vráceno zadavateli s důvodem |
| 1. Stav „před“ | `17001` `programator` (*Worker*) | Založí čerstvý klon `wt-worker` z aktuální hlavní větve a E2E testem pořídí snímky výchozího stavu. | Snímky `před` |
| 2. Úprava | `17001` `programator` (*Worker*) | Provede jednu úpravu v povolených cestách (kapitola 2); nejvýše 2 samo-opravy. | Diff |
| 3. Stav „po“ | `17001` `programator` (*Worker*) | Spustí E2E test dotčeného procesu a pořídí snímky nového stavu. | Snímky `po`, výstup testů |
| 4. Deterministická kontrola | **`AigisCode`** + **`gitleaks`** + kontrola testů | Ověří povolené cesty, hranice vrstev, nepřítomnost tajemství a **integritu E2E asercí** (žádné smazané `expect`, `.skip` ani změkčení kontrol). | `0` porušení / FAIL |
| 5. Nezávislý posudek | `17004` `klicnik` (*Judge*) | Ve `wt-judge` dostane výhradně Zadání, diff, výstup testů a snímky; posoudí shodu se Zadáním, integritu testů, nepřítomnost PII ve snímcích a bezpečnost. | PASS / FAIL s důvodem |
| 6. Náhled a kontrola hlavní větve | `17005` `ai-provoz` | Ověří, že se hlavní větev od založení `wt-worker` neposunula. Neposunula-li se, založí při PASS položku v `Decisions` s diffem a snímky `před → po` a s identifikátorem commitu, který `Judge` posoudil. Posunula-li se, sám nic nepřepisuje: vrátí úpravu Workerovi, ten ve `wt-worker` provede rebase, zopakuje krok 3 a úprava projde znovu kroky 4 a 5. | Položka v `Decisions` / návrat ke kroku 3 |
| 7. Rozhodnutí | `1001` | `mutation_confirm` → sloučí se (`fast-forward`) právě ten commit, který `Judge` posoudil, a jen pokud stále sedí na aktuální `main`; jinak se nic neslučuje a úprava se vrací ke kroku 6. `mutation_cancel` → zahození. | Sloučeno / zahozeno / návrat ke kroku 6 |

Rebase je nová verze diffu: nikdy se neslučuje commit, který `Judge` neviděl. Opakování kroků 3–5 po rebase běží uvnitř téhož časového boxu a nepočítá se jako samo-oprava; nestihne-li se, platí kapitola 8.

Po sloučení proběhne běžný běh na hlavní větvi a `manual-builder` vygeneruje novou verzi příručky, takže změna UI se do příručky propíše sama.

---

## 6. Kritéria přijetí (vše musí platit současně)

- [ ] Diff zasahuje pouze do povolených cest (kapitola 2) a do žádné zakázané (kapitola 3).
- [ ] `AigisCode` i `gitleaks` hlásí `0` porušení.
- [ ] E2E test dotčeného procesu prošel proti testovacímu prostředí se syntetickými daty; **integrita testových asercí** zůstala neporušená (žádné odstraněné ani oslabené `expect`, žádné `.skip` nebo podmínkové obcházení).
- [ ] Hlavní větev (`main`) je shodná se základem testovaného diffu a slučovaný commit je tentýž, ke kterému `Judge` vydal PASS (po rebase proběhly kroky 3–5 znovu).
- [ ] Ke každé změněné obrazovce nebo sestavě existuje dvojice snímků `před → po` a snímek `po` odpovídá poli `pozadovany_stav`.
- [ ] Ve snímcích, diffu ani v popisu nejsou osobní údaje ani tajemství (vč. viditelných textů mimo `[data-e2e-mask]`).
- [ ] Limity z kapitoly 7 nebyly překročeny.
- [ ] `Judge` (`17004`) vydal PASS a běžel na modelu jiného výrobce než `Worker`.
- [ ] `1001` potvrdil položku v `Decisions` akcí `mutation_confirm`.

---

## 7. Limity

| Limit | Hodnota | Stav |
| :--- | :--- | :--- |
| Časový box (převzetí požadavku → položka v `Decisions`) | 30 minut | závazné (zadání S6) |
| Počet úprav na iteraci | 1 požadavek = 1 formulář nebo 1 tisková sestava | závazné |
| Počet samo-oprav Workera | nejvýše 2, poté `FAIL_CLOSED` | závazné (kanon: max. 15 kroků / 2 samo-opravy) |
| Rozsah diffu na iteraci (počet souborů a změněných řádků) | `NÁVRH — ke schválení 1001` | k rozhodnutí |
| Rozdělení 30 minut mezi Workera, Judge a přípravu náhledu | `NÁVRH — ke schválení 1001` | k rozhodnutí |
| Počet souběžně rozpracovaných požadavků | `NÁVRH — ke schválení 1001` | k rozhodnutí |
| Rozpočet | uvnitř stávajících alokací `17001` (*Worker*), `17004` (*Judge*), `17005` (třídění) a stropu `470 USD / měsíc`, shodně s pravidlem 7 v `README.md`; při vyčerpání kvóty `PAUSED` | závazné |

---

## 8. Neúspěch a eskalace

- Při překročení časového boxu, překročení limitu, FAIL kterékoliv kontroly nebo FAIL od `Judge` se změna **zahodí**: klon `wt-worker` se smaže, větev se neslučuje a neopravuje se „ještě jednou rychle“.
- `17005` zapíše do požadavku důvod (který krok selhal, výstup kontroly) a eskaluje ho člověku — `1001` v nejbližším denním balíčku `Decisions` (07:30 / 16:30). Člověk rozhodne, zda požadavek zrušit, upřesnit zadání, nebo převést do běžného vývojového postupu.
- Stejný požadavek se do smyčky nevrací bez nového nebo upřesněného zadání (žádné opakování téhož neúspěšného kroku).
- Pokus zasáhnout do `cad-urs-engine` nebo `Hard-Stop` zámků `db_hr_lide` se navíc hlásí do `#17-it-secops` jako bezpečnostní událost.
