# Blok 18 · Balíček S6 — Samo-dokumentující E2E testy a 30min vývojová smyčka UI · Verze 3.31

Tento dokument je řídicím dokumentem **`Bloku 18`** Rozvojové Etapy II společnosti **Polarita s.r.o.** (balíček `S6` ze zásobníku `03-NAVRHY-BALICKU-NA-POZDEJI.md`, release `Polarita-3.31`). Definuje dvě navazující věci: *(1)* **živou ilustrovanou příručku** — každý end-to-end test klíčového firemního procesu v **`Playwright`** pořizuje během běhu v `Gitea Actions` popsané snímky obrazovky a generátor **`manual-builder`** z nich po každém úspěšném běhu na hlavní větvi skládá vždy aktuální provozní příručku (`Markdown → PDF`) pro zaškolení montérů, skladníků a partnerů `SUB`; *(2)* **řízenou 30minutovou vývojovou smyčku** výhradně pro ne-normové UI a tiskové sestavy nad **`metadata-schema-kernel`**, ve které `17001 programator` (*Worker*) připraví úpravu v odděleném klonu **`wt-worker`**, **`AigisCode`** + `17004 klicnik` (*Judge*) ji ověří v **`wt-judge`** a do **`Decisions`** dorazí náhled se screenshoty **`před → po`**. Blok 18 lze spustit až po `12/12 PASS` Go-Live Gate (`Blok 12`), nezávisí na `Blocích 13–17`, nezakládá žádného nového `ai` zaměstnance ani oddělení a celý běží uvnitř stropu **`470 USD / měsíc`**.

Soubory balíčku: tento `README.md`, vzorový test [`priklad/karta-spisu.spec.ts`](priklad/karta-spisu.spec.ts), sdílená pomocná funkce [`priklad/krok.ts`](priklad/krok.ts) a pravidla fronty [`fronta-30min-smycka.md`](fronta-30min-smycka.md).

---

## 1. Seznam softwaru a modulů

| Oblast | Vybraný software / modul | Kanál / Režim | Role a použití | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **E2E testy klíčových procesů s popsanými screenshoty** | **`Playwright`** *(`TypeScript`, testovací běžec `@playwright/test`)* + sdílená pomocná funkce **`krok(page, popisek)`** *(`priklad/krok.ts`; každý test si ji naváže na svou kapitolu voláním `vytvorKrok(kapitola)`)* | `latest` *(open-source; běh výhradně proti testovacímu prostředí se syntetickými daty)* | Automaticky prochází 6 pokrytých procesů (360° Karta spisu, `portal-spolupracovniku`, výdej z `Elektro WMS`, Elektronický stavební deník, `mutation_confirm` v `Decisions`, podání ISDS v Podatelně); každý krok má český popisek, pořídí snímek obrazovky a zapíše řádek do manifestu `JSON`. | `17001` `programator` / `17002` `webmaster` |
| **Generátor živé příručky** | Vlastní modul **`manual-builder`** *(manifest `JSON` + screenshoty → `Markdown` → `PDF` sazbou `Typst`, která už je součástí sady)* | `latest` *(vlastní čistý kód v `Gitea`)* | Z manifestů a snímků složí kapitoly příručky (1 test = 1 kapitola, 1 krok = 1 odstavec + obrázek), uloží `Markdown` i `PDF` do Vaultu `/srv/polarita/vault/07-IT-a-Architektura/` a vystaví školicí kopii pro montéry, skladníky a partnery `SUB` (kanál distribuce kopie: `NÁVRH — ke schválení 1001`). | `17002` `webmaster` *(provoz `17005` `ai-provoz`)* |
| **CI brána a plánovač běhů** | **`Gitea Actions`** *(lokální CI v `Gitea`; vyhrazená instance `gitea-runner` v `app_internal`, režim `host`, bez přístupu k produkčním tajemstvím)* | `latest` *(self-hosted za VPN `Headscale`; workflow soubory mění jen `1001` / `17004`)* | Spouští E2E testy u každého pull requestu a na hlavní větvi; příručku generuje a publikuje pouze po úspěšném běhu na hlavní větvi; neúspěšný běh nic nepřepisuje. | `17005` `ai-provoz` / `17003` `spravce-site` |
| **Izolace tvůrce a kontrolora 30min smyčky** | **`wt-worker`** / **`wt-judge`** *(dva oddělené klony repozitáře, každý s vlastním `.git`, ne sdílené worktree)* | `latest` *(vzor `Worker / Judge` z `Bloku 7`)* | `Worker` píše úpravu ve `wt-worker`; `Judge` běží ve `wt-judge` na modelu jiného výrobce a dostává výhradně Zadání, diff, výstup testů a screenshoty — nikdy úvahy tvůrce. | `17001` `programator` *(Worker)* / `17004` `klicnik` *(Judge)* |
| **Statický strážce hranic smyčky** | **`AigisCode`** *(`Draivix/aigiscode`, `MIT`)* + **`gitleaks`** | `latest` *(čistý open-source)* | Deterministicky odmítne diff, který sahá mimo povolené cesty smyčky (`cad-urs-engine`, `Hard-Stop` zámky `db_hr_lide`, `Clean Room`, vendor schémata, autorizace) nebo obsahuje tajemství. | `17004` `klicnik` / `17005` `ai-provoz` |
| **Předmět a výstup smyčky** | **`metadata-schema-kernel`** *(formuláře a tiskové sestavy)* + fronta **`Decisions`** *(`mutation_confirm` / `mutation_cancel`)* | `latest` *(vlastní kód / `Paperclip`)* | Smyčka upravuje pouze prezentační vrstvu vlastních formulářů a interních tiskových sestav; výsledkem je položka v `Decisions` s diffem a screenshoty `před → po`, kterou potvrzuje `1001`. | `17001` `programator` / garant `1001` |

---

## 2. Architektonická pravidla

1. **Testy běží výhradně proti testovacímu prostředí se syntetickými daty — nikdy proti produkci:**
   * E2E testy se připojují pouze na adresu z proměnné prostředí `POLARITA_E2E_BASE_URL`; v repozitáři není žádná skutečná adresa. Testovací prostředí tvoří samostatné instance v `Incus` (`0× Docker`), jejichž databáze vznikají z migrací a syntetického seedu, nikdy z kopie produkčních dat.
   * Ve screenshotech, manifestech ani v příručce nesmí být žádné osobní údaje (`0` PII): osoby, firmy, adresy i spisy `POL-RRRR-NNNNN` jsou smyšlené a zjevně označené jako vzorové; přihlašovací údaje testovacích účtů se čtou z `OpenBao`, nikdy z repozitáře ani z logu. **Upozornění na screenshoty:** maskování prvků `[data-e2e-mask]` chrání jen výslovně označené uzly DOM a neochrání uniklé PII v hláškách nebo vstupních polích — základem ochrany je vždy čistě syntetický seed a následná kontrola snímků před publikací.
   * Pro přihlášení přes `Keycloak` OIDC preferujte v reálné sadě oddělený *setup* projekt s `storageState` (`Playwright`), aby se zbytečně nefotilo přihlášení v každé kapitole a fungovaly i toky s `MFA` / `Passkey`.
   * Podání ISDS se testuje výhradně proti testovacímu prostředí `czebox.cz`; produkční endpoint `ws1.mojedatovaschranka.cz` ani schránka `w9bbdva` se v testech nepoužívají.
2. **Každý krok testu má český popisek, který se stává textem příručky:**
   * Test nevolá `page.screenshot()` přímo, ale pomocnou funkci `krok(page, popisek)`. Funkce je napsána jednou ve sdíleném souboru `krok.ts`; každý soubor testu si ji na začátku naváže na svou kapitolu (`const krok = vytvorKrok({ id, title })`), takže se kód kroku nekopíruje a kapitola nemůže zapisovat do manifestu jiné kapitoly. Popisek je celá česká věta psaná pro montéra nebo skladníka (co udělat a co uvidí), ne technická poznámka pro vývojáře.
   * Funkce zapíše pořadí kroku, popisek a název souboru snímku do manifestu `JSON`; manifest je jediným vstupem `manual-builder`, takže text příručky nelze změnit jinak než změnou testu (příručka a chování aplikace se nemohou rozejít).
3. **Pokryté procesy (minimální rozsah příručky):**
   * *(1)* 360° Karta spisu `POL-RRRR-NNNNN`, *(2)* `portal-spolupracovniku`, *(3)* výdej z `Elektro WMS`, *(4)* zápis do Elektronického stavebního deníku, *(5)* schválení `mutation_confirm` v `Decisions`, *(6)* podání ISDS v Podatelně.
   * Všech šest procesů pochází z `Bloků 7–11` Etapy I; Blok 18 proto nevyžaduje žádnou službu z jiného rozvojového bloku.
4. **Příručka se generuje po každém úspěšném běhu na hlavní větvi:**
   * Po úspěšném běhu všech E2E testů na hlavní větvi `manual-builder` vygeneruje novou verzi příručky (`Markdown` + `PDF`), uloží ji do Vaultu `07-IT-a-Architektura` a vystaví školicí kopii; verze příručky nese identifikátor commitu, ze kterého vznikla.
   * Při neúspěšném běhu se příručka negeneruje a poslední platná verze zůstává beze změny; běhy u pull requestů příručku nikdy nepublikují.
5. **30min smyčka je VÝHRADNĚ pro ne-normové UI a tiskové sestavy nad `metadata-schema-kernel`:**
   * `17001 programator` pracuje jako `Worker` v odděleném klonu `wt-worker`; `AigisCode` + `17004 klicnik` pracují jako `Judge` ve `wt-judge` a ověřují úpravu E2E testy; výstupem je náhled se screenshoty `před → po` ve frontě `Decisions`, kde změnu potvrdí nebo zamítne `1001` (`mutation_confirm` / `mutation_cancel`).
   * **`Worker` (`17001`)**, **`Judge` (`17004` + `AigisCode`)** a kontrola hlavní větve před sloučením zajišťují, že v diffu neslábnou E2E aserce (žádné mazání `expect` ani `.skip`), že `wt-worker` nemá nekontrolovaný rozchod proti `main` (po každém rebase se úprava vrací k `Judge`, do `Decisions` jde jen commit, který `Judge` skutečně posoudil) a že snímky `před → po` neobsahují PII.
   * **Výslovný zákaz:** smyčka nikdy nezasahuje do normového jádra ČSN `cad-urs-engine` ani do `Hard-Stop` zámků `db_hr_lide`; stejně tak ne do `Clean Room` pohledů, vendor schémat cizích aplikací, autorizace a tajemství. Úplný výčet zakázaných oblastí i výčet povolených cest je v `fronta-30min-smycka.md` (kapitoly 2 a 3).
6. **Limit změn, časový box a zahození při neúspěchu:**
   * Jedna iterace = jeden požadavek = jeden formulář nebo jedna tisková sestava; platí limit rozsahu změny na iteraci (číselná hodnota je v `fronta-30min-smycka.md` vedena jako `NÁVRH — ke schválení 1001`) a kanonický limit nejvýše 2 samo-oprav.
   * Časový box je 30 minut od převzetí požadavku po položku v `Decisions`. Při překročení času, překročení limitu nebo neúspěchu kterékoliv kontroly se změna zahodí (klon `wt-worker` se smaže, nic se neslučuje) a požadavek se eskaluje člověku.
7. **Vše uvnitř stropu `470 USD / měsíc`:**
   * Blok 18 nezvyšuje žádný rozpočet: spotřeba 30min smyčky se účtuje do stávajících alokací `17001` (*Worker*), `17004` (*Judge*) a `17005` (třídění); příprava E2E testů a modulu `manual-builder` do alokací `17001` a `17002`. Při vyčerpání kvóty se smyčka pozastaví (`PAUSED`) stejně jako ostatní nekritické úlohy. Samotné E2E testy a `manual-builder` jsou deterministické a nevolají žádné placené API.

---

## 3. Pokyny pro `ai` (Prompty)

### Prompt 1 — E2E testy `Playwright` s funkcí `krok(page, popisek)` nad testovacím prostředím (`pro 17001 programator` + `17002 webmaster`)

```text
Jsi 17001 programator ve spolupráci s 17002 webmaster. Připrav v Bloku 18 sadu end-to-end testů Playwright (latest), které zároveň dokumentují klíčové firemní procesy Polarita s.r.o.:

1. Testovací prostředí a bezpečnostní hranice:
   - Testy smí běžet pouze proti testovacímu prostředí v Incus se syntetickými daty. Adresu čti VÝHRADNĚ z proměnné prostředí POLARITA_E2E_BASE_URL; do repozitáře nikdy nezapisuj žádnou skutečnou adresu.
   - Databáze testovacího prostředí vytvářej z migrací a syntetického seedu, nikdy z kopie produkce. V seedu nesmí být žádné osobní údaje (0 PII); osoby, firmy, adresy a spisy POL-RRRR-NNNNN jsou smyšlené.
   - Přihlašovací údaje testovacích účtů načítej z OpenBao do proměnných prostředí běhu; nikdy je nevypisuj do logu, manifestu ani screenshotu.
   - Před prvním krokem každého testu ověř, že stránka zobrazuje označení testovacího prostředí; pokud ne, test okamžitě ukonči (FAIL_CLOSED).
2. Pomocná funkce krok(page, popisek):
   - Vyjdi ze vzoru balicky/S6-ziva-prirucka-e2e/priklad/karta-spisu.spec.ts a sdílené pomocné funkce priklad/krok.ts (vzory nebyly spuštěny, selektory přizpůsob skutečné aplikaci). Funkci krok nekopíruj do jednotlivých testů: každý soubor testu si ji naváže na svou kapitolu voláním vytvorKrok s jedinečným id kapitoly.
   - Každý krok pořídí snímek obrazovky a zapíše do manifestu JSON pořadí, český popisek a název souboru. Popisek piš jako celou českou větu pro montéra nebo skladníka.
3. Pokryté procesy (každý jako samostatný soubor testu = jedna kapitola příručky):
   - 360° Karta spisu, portal-spolupracovniku, výdej z Elektro WMS, zápis do Elektronického stavebního deníku, schválení mutation_confirm v Decisions, podání ISDS v Podatelně.
   - Podání ISDS testuj výhradně proti czebox.cz; produkční endpoint ws1.mojedatovaschranka.cz ani schránku w9bbdva v testech nepoužívej.
4. Výstup:
   - Otevři pull request v Gitea; připoj výpis běhu testů a seznam pořízených snímků. Nic nevydávej za spuštěné, pokud to neproběhlo.
```

### Prompt 2 — Generátor `manual-builder` a pipeline `Gitea Actions` pro živou příručku (`pro 17002 webmaster` + `17005 ai-provoz`)

```text
Jsi 17002 webmaster ve spolupráci s 17005 ai-provoz. Zprovozni generování živé příručky z výstupů E2E testů:

1. Modul manual-builder (latest, vlastní kód v Gitea):
   - Vstupem jsou pouze manifesty JSON a snímky obrazovky z běhu Playwright. Jeden test = jedna kapitola, jeden krok = jeden odstavec s obrázkem.
   - Výstupem je příručka v Markdownu a v PDF (sazba Typst). Na titulní straně uveď datum vygenerování a identifikátor commitu.
   - Modul je deterministický: nevolá žádný jazykový model ani placené API a text příručky nepřepisuje.
2. Pipeline v Gitea Actions (latest):
   - U každého pull requestu spusť E2E testy a ulož snímky jako artefakt běhu; příručku nepublikuj.
   - Po úspěšném běhu na hlavní větvi spusť manual-builder, ulož Markdown i PDF do Vaultu /srv/polarita/vault/07-IT-a-Architektura/ a vystav školicí kopii pro montéry, skladníky a partnery SUB.
   - Při neúspěšném běhu příručku negeneruj; poslední platná verze zůstává beze změny.
3. Kontrola před publikací:
   - Před uložením do Vaultu spusť kontrolu, že manifesty ani texty neobsahují osobní údaje ani tajemství (gitleaks + kontrola vzorů PII). Při nálezu publikaci zastav a založ položku v Decisions.
4. Výstup:
   - Zapiš do Vaultu 07-IT-a-Architektura protokol prvního úspěšného vygenerování (commit, počet kapitol, počet snímků).
```

### Prompt 3 — Řízená 30minutová smyčka `Worker / Judge` pro ne-normové UI a tiskové sestavy (`pro 17001 programator`, `17004 klicnik` a `17005 ai-provoz`)

```text
Zaveď a provozuj 30minutovou vývojovou smyčku podle balicky/S6-ziva-prirucka-e2e/fronta-30min-smycka.md. Role: 17005 ai-provoz třídí frontu a měří čas, 17001 programator je Worker, 17004 klicnik s nástrojem AigisCode je Judge.

1. Třídění požadavku (17005 ai-provoz):
   - Přijmi pouze požadavek ve vstupní šabloně, který se týká ne-normového UI nebo interní tiskové sestavy nad metadata-schema-kernel. Vše ostatní vrať zadavateli s odkazem na běžný vývojový postup.
   - Spusť časový box 30 minut.
2. Worker (17001 programator):
   - Pracuj výhradně v odděleném klonu wt-worker (vlastní .git, ne sdílený worktree). Před úpravou pořiď E2E testem snímky stavu „před“.
   - Proveď jednu úpravu v povolených cestách (výčet v kapitole 2 pravidel fronty) a dodrž limit změn na iteraci. Nikdy nesahej do cad-urs-engine, Hard-Stop zámků db_hr_lide, Clean Room pohledů, vendor schémat ani autorizace.
   - Pořiď snímky stavu „po“ a předej Zadání, diff, výstup testů a snímky.
3. Judge (AigisCode + 17004 klicnik):
   - Pracuj ve wt-judge (druhý oddělený klon) na modelu jiného výrobce než Worker. Dostáváš výhradně Zadání, diff, výstup testů a snímky; úvahy tvůrce nečti.
   - Ověř: 0 porušení v AigisCode a gitleaks, diff jen v povolených cestách, E2E aserce nebyly oslabeny ani přeskočeny, E2E testy dotčeného procesu prošly proti aktuální hlavní větvi (bez rozchodu s main), snímky „před“ a „po“ odpovídají Zadání, žádné osobní údaje.
4. Výsledek:
   - PASS: založ položku v Decisions s diffem a snímky „před -> po“; sloučit lze až po mutation_confirm od 1001. Posunula-li se mezitím hlavní větev, Worker provede rebase, znovu pořídí snímky a úprava se vrací k Judge; do Decisions jde jen commit, který Judge posoudil.
   - FAIL, překročení limitu nebo času: změnu zahoď (smaž klon wt-worker, nic neslučuj), zapiš důvod a eskaluj člověku. Stejný požadavek nespouštěj znovu bez nového zadání.
```

---

## 4. Ověřitelné podmínky dokončení Bloku 18

- [ ] E2E testy v **`Playwright (latest)`** pokrývají všech 6 procesů (360° Karta spisu, `portal-spolupracovniku`, výdej z `Elektro WMS`, Elektronický stavební deník, `mutation_confirm` v `Decisions`, podání ISDS v Podatelně) a procházejí v `Gitea Actions` proti testovacímu prostředí se syntetickými daty.
- [ ] Žádný test neobsahuje skutečnou adresu (pouze `POLARITA_E2E_BASE_URL`), podání ISDS míří výhradně na `czebox.cz` a kontrola výstupů nenašla žádné PII ani tajemství ve screenshotech, manifestech a příručce.
- [ ] Každý krok každého testu má český popisek a záznam v manifestu `JSON`; **`manual-builder`** z nich po úspěšném běhu na hlavní větvi vygeneroval příručku (`Markdown` + `PDF`) uloženou ve Vaultu `07-IT-a-Architektura` včetně školicí kopie.
- [ ] Záměrně rozbitý test na hlavní větvi prokazatelně nezpůsobil přepsání poslední platné verze příručky.
- [ ] 30min smyčka prošla zkušebním požadavkem od vstupní šablony po položku v `Decisions` se screenshoty `před → po` a změna byla sloučena až po `mutation_confirm` od `1001`.
- [ ] Zkušební požadavek mířící do `cad-urs-engine` a zkušební požadavek mířící na `Hard-Stop` zámek `db_hr_lide` byly odmítnuty (`AigisCode` + `17004`), zahozeny a eskalovány člověku; totéž při umělém překročení 30 minut.
- [ ] Spotřeba Bloku 18 je vidět ve FinOps přehledu uvnitř stropu `470 USD / měsíc` bez navýšení jakékoliv alokace.

---

## 5. Stav ve Verzi 3.31

**Hotové v této složce (dokumentace a vzory):**

- `README.md` — řídicí dokument Bloku 18 (seznam softwaru, pravidla, tři prompty, podmínky dokončení).
- `priklad/karta-spisu.spec.ts` — vzorový test `Playwright` jedné kapitoly příručky. **Vzor nebyl spuštěn** — testovaná aplikace ani testovací prostředí zatím neexistují; selektory a texty obrazovek jsou ilustrační.
- `priklad/krok.ts` — sdílená pomocná funkce `krok(page, popisek)` se zápisem do manifestu `JSON`, kterou si každý test naváže na svou kapitolu (`vytvorKrok`). **Vzor nebyl spuštěn ani přeložen** kompilátorem `TypeScript`.
- `fronta-30min-smycka.md` — pravidla fronty 30min smyčky (co smí a nesmí, vstupní šablona, kroky, kritéria přijetí, limity).

**Vyžaduje živý server `polarita-hq` (připraveno k nasazení, neprovedeno):**

- Testovací prostředí v `Incus` se syntetickým seedem, běžec `Gitea Actions` a skutečný běh E2E testů.
- Vývoj modulu `manual-builder`, první vygenerování příručky a její uložení do Vaultu `07-IT-a-Architektura`.
- Zprovoznění 30min smyčky (`wt-worker` / `wt-judge`, pravidla `AigisCode`, položky v `Decisions`) a ověření podmínek z kapitoly 4.

Přijetí Bloku 18 vyžaduje spuštění vzorového scénáře v ředitelství a záznam výsledku do protokolu. Položky vedené jako `NÁVRH — ke schválení 1001`: číselný limit rozsahu změny na iteraci, rozdělení 30 minut mezi role, počet souběžných požadavků a umístění fronty (vše v `fronta-30min-smycka.md`) a kanál distribuce školicí kopie příručky.
