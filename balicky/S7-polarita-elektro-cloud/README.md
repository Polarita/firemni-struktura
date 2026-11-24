# Blok 19 · Balíček S7 — Polarita Elektro Cloud (oborový SaaS spin-off, N9) · Verze 3.2.2

Tento dokument je řídicím dokumentem **`Bloku 19`** Strategické Etapy III společnosti **Polarita s.r.o.** (balíček `S7`, vlna `N9`, release `Polarita-3.2.2`). Vychází ze strategického vzoru `TRITON IT → Draivix`: firma si nejprve postaví, v ostrém provozu odladí a vyčistí vlastní `ai-first` systém (Etapa I, `Bloky 0–12`, na serveru `polarita-hq`) a teprve po objektivně změřené bráně **`Go / No-Go`** jej otevře trhu jako oborovou SaaS platformu **„Polarita Elektro Cloud“** pro elektro firmy a revizní techniky v ČR a SR. Platforma běží ve **vlastním produkčním klastru zcela odděleném od `polarita-hq`**; všichni tenanti sdílejí jednotné aplikační schéma s vynuceným **`PostgreSQL Row-Level Security`** (`FORCE` + `AS RESTRICTIVE` + složený klíč `(tenant_id, id)`, s možností vyhrazeného schématu jen jako volitelného enterprise nadstandardu), vlastní šifrovací klíč v **`OpenBao`** a vlastní režim **`Clean Room`**. Ve Verzi 3.2.2 je připravena architektura, brána a vzory — **Blok 19 se nespouští, dokud brána není splněna a schválena `1001`**.

Soubory balíčku: tento `README.md`, brána [`go-no-go-gate.md`](go-no-go-gate.md), vzor izolace [`rls-vzor.sql`](rls-vzor.sql) s doplňkovým testem přihlášení a recyklovaného spojení [`rls-pool-test.sql`](rls-pool-test.sql), struktura tarifů [`tarify-saas.md`](tarify-saas.md) a osnova podmínek [`licencni-podminky-osnova.md`](licencni-podminky-osnova.md).

---

## 1. Seznam softwaru a modulů

| Oblast | Vybraný software / modul | Kanál / Režim | Role a použití | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Brána spuštění Strategické Etapy III** | Protokol **`Go / No-Go`** *(`go-no-go-gate.md`)* nad daty z `centralni-lhutnik-a-objekty`, `cad-urs-engine`, `Eval Suite` a Partnerského provizního ledgeru | dokument + měření *(jen agregované počty, `0` PII)* | Pět objektivních kritérií; `ai` připraví pouze koncept protokolu (`DRAFT`), rozhodnutí `GO` podepisuje výhradně `1001`. | `11001` `ceo` / `17005` `ai-provoz` *(rozhoduje `1001`)* |
| **Oddělený produkční klastr SaaS** | **`Incus`** + **`OpenTofu`** *(stejný stack jako `polarita-hq`, jiný hardware, jiné sítě, jiné zálohy)* | `latest` *(`0× Docker` na hostiteli)* | Samostatný klastr bez síťové, databázové a klíčové vazby na `polarita-hq`; se zdrojovým kódem ho spojují jen podepsané release tagy z `Gitea`. | `17003` `spravce-site` *(audit `17004` `klicnik`)* |
| **Multi-tenant datová vrstva** | **`PostgreSQL`** *(sdílené schéma + `FORCE` a `AS RESTRICTIVE` `ROW LEVEL SECURITY` + složený PK `(tenant_id, id)`)* řízený **`metadata-schema-kernel`** | `latest` *(vzor `rls-vzor.sql`)* | Primární model: jednotné sdílené schéma (kvůli `PgBouncer` a jediné migraci), každá tabulka nese `tenant_id`, omezující politiku `AS RESTRICTIVE` vytvořenou `TO PUBLIC` (váže každou současnou i budoucí roli) podle `current_tenant_id()` a složený klíč s `tenant_id`; aplikační role nemá `BYPASSRLS` ani `SUPERUSER` a do registru tenantů včetně stavu tenanta (aktivní / deaktivovaný) zapisuje jen vyhrazená role pro zakládání tenantů. Vyhrazené schéma je jen volitelná nadstavba. | `17001` `programator` *(Judge `17004` `klicnik`)* |
| **Klíče, tajemství a identita tenantů** | **`OpenBao`** *(vlastní instance klastru, vlastní šifrovací klíč na tenant)* + **`Keycloak`** *(OIDC SSO)* | `latest` | Citlivá pole tenanta se šifrují jeho vlastním klíčem; `tenant_id` se odvozuje z ověřeného tokenu OIDC, nikdy ze vstupu klienta: autentizační brána po ověření vydá krátkodobý neprůhledný token relace a na tenanta si jej převádí databáze sama (aplikační role tenanta nikdy neuvádí přímo). | `17004` `klicnik` / `17003` `spravce-site` |
| **`Clean Room` na tenant** | `Read-Only` pohledy s maskováním PII *(vzor z `Bloku 5`)* | `latest` | `ai` asistent tenanta čte osobní údaje jen přes maskované pohledy téhož tenanta; žádný sdílený kontext ani paměť mezi tenanty. | `17004` `klicnik` / `17001` `programator` |
| **Produktové moduly SaaS edice** | **`centralni-lhutnik-a-objekty`**, **`cad-urs-engine`**, **`cz-sk-registry-kernel`**, **`WhisperX`** | `latest` *(vydání z tagů v `Gitea`)* | Digitální kniha objektu a Lhůtník, výpočty a Výrobní pas rozváděče, stavební deník, registry ČR / SR — viz pravidlo 4. | `17001` `programator` *(normy `15002` `normovac`)* |
| **Tarify a měřený rozpočet tokenů** | Měření spotřeby na tenant s tvrdým stropem *(rozšíření FinOps vrstvy)* | `latest` *(parametry v `tarify-saas.md`)* | Předplatné za celou firmu bez příplatku za montéra; po vyčerpání rozpočtu tokenů se zastaví jen `ai` funkce tenanta. | `17005` `ai-provoz` / `16001` `ucetni` |
| **Kvalita vydání a právní rámec** | **`Eval Suite`** + **`AigisCode`** + `Gitea Actions`; licenční podmínky *(`licencni-podminky-osnova.md`)* | `latest` | Vydání do SaaS klastru jen při `100 %` `Eval Suite` a prošlých testech izolace tenantů; podmínky reviduje `15001` a advokát. | `17005` `ai-provoz` / `15001` `pravni-specialista` |

---

## 2. Architektonická pravidla

1. **Brána `Go / No-Go` — dokud není splněna a schválena `1001`, Blok 19 se nespouští:**
   * Musí platit současně: *(a)* **12–18 měsíců bezchybného interního provozu** na `polarita-hq`, *(b)* **≥ 100 aktivně spravovaných objektů** SVJ / B2B v Digitální knize objektu, *(c)* **≥ 500 vydaných revizních zpráv / Výrobních pasů rozváděčů**, *(d)* **stabilní `100 %` `Eval Suite`**, *(e)* **≥ 15 aktivních `Certified Partner SUB`**.
   * Měření, zdroje dat a rozhodovací protokol s podpisem `1001` jsou v `go-no-go-gate.md`. Nesplnění kteréhokoliv kritéria znamená `NO-GO`; `ai` nesmí bránu obejít, zmírnit ani prohlásit za splněnou.
   * Před podpisem `GO` se smí pouze udržovat dokumentace a vzory v této složce; nesmí se pořizovat hardware klastru, zakládat tenanti ani uzavírat smlouvy se zákazníky.
2. **Vlastní produkční klastr a žádná data interního provozu Polarity v SaaS:**
   * SaaS klastr je fyzicky i logicky oddělený od `polarita-hq`: vlastní `Incus`, sítě, `PostgreSQL`, `OpenBao`, zálohy a monitoring. Mezi klastry není žádné databázové spojení, sdílený klíč, sdílený Vault ani sdílená záloha.
   * Do SaaS klastru se nikdy nepřenášejí data interního provozu Polarity (spisy `POL-RRRR-NNNNN`, `db_hr_lide`, `db_gdpr_zkousky`, hovory, účetnictví, Vault). Vlastní zakázky Polarita s.r.o. dál zpracovává výhradně na `polarita-hq`.
3. **Multi-tenancy — sdílené schéma + vynucená `AS RESTRICTIVE` `Row-Level Security` + vlastní klíč + vlastní `Clean Room`:**
   * Primárním modelem je sdílené aplikační schéma (kvůli sdružování spojení `PgBouncer` a jednotným migracím): každá tabulka má složený primární klíč `(tenant_id, id)` (bez globální sekvence), `ENABLE` i `FORCE ROW LEVEL SECURITY` a omezující politiku `AS RESTRICTIVE` vytvořenou `TO PUBLIC` podle bezpečného `current_tenant_id()`. Vyhrazené schéma pro jednotlivého tenanta je jen volitelný enterprise nadstandard. Aplikace se připojuje rolí bez `BYPASSRLS` a kontext tenanta předává jen krátkodobým tokenem relace vydaným autentizační bránou (`app.tenant_token`), nikdy přímým uvedením tenanta; chybějící, neplatný nebo prošlý token znamená `0` řádků (`FAIL_CLOSED`). Expirace tokenu se posuzuje vůči času začátku každého příkazu, ne vůči začátku transakce, takže otevřená transakce prošlý token při životě neudrží; délka příkazů a transakcí aplikační role je proto omezena výrazně pod životnost tokenu. Registr tenantů zapisuje výhradně vyhrazená role pro zakládání tenantů a vede i stav tenanta: ukončení je auditovaná deaktivace (čas a odkaz na rozhodnutí), která se ověřuje při vydání i při každém použití tokenu — deaktivovanému tenantovi se nový token nevydá a dříve vydané tokeny přestanou platit prvním dalším příkazem; tenant bez řádku stavu přístup nemá. Každá změna stavu ve stejné transakci zvýší generaci relací tenanta, takže relace vydané před deaktivací zůstávají revokované i po reaktivaci a uživatelé se musí přihlásit znovu. Token se nastavuje jen na transakci, nikdy na relaci; že kontext nepřežije `COMMIT` ani `ROLLBACK` na znovu použitém spojení, dokládá samostatný test přes skutečné přihlášení aplikační role (`rls-pool-test.sql`). Vlastník objektů pod `FORCE` nevidí žádná doménová data. Každá funkce `SECURITY DEFINER` má `search_path` připnutý na výslovně povolenou hodnotu a katalogový test kontroluje přímo tuto hodnotu. Známé meze vzoru (držitel platného tokenu, kompromitace brány, migrace napříč tenanty, dlouhý příkaz přes okamžik expirace, deaktivace nemaže data) jsou vyjmenovány na konci `rls-vzor.sql`. Vzor včetně testů „tenant A nevidí tenanta B“ a `Clean Room` pohledů s `security_invoker = true` je v `rls-vzor.sql`.
   * Každý tenant má vlastní šifrovací klíč v `OpenBao`; smazání klíče po ukončení smlouvy a uplynutí lhůt činí jeho data nečitelnými i v zálohách.
   * `ai` asistent pracuje vždy v kontextu jediného tenanta přes jeho `Clean Room`; data tenanta se nepoužívají k učení ani k odpovědím jinému tenantovi.
4. **Produktový rozsah SaaS edice (čtyři body zadání):**
   * *(1)* **Digitální kniha objektu s QR štítky + 48h `ai` vytěžení starých šanonů + Centrální Lhůtník** — s logem předplatitelské elektro firmy a klientským portálem pro její vlastní SVJ a průmyslové zákazníky.
   * *(2)* **`ai` asistent revizního technika (`≤ 4 h`), rozpočtáře CS ÚRS a hlasové kanceláře (`WhisperX`)** — přepis naměřených tabulek, fotek závad a telefonních dohod o vícepracích, kontrola 9 vrstev přípomocí CS ÚRS přes tlačítka `„Pracuj“` na 360° Kartě zakázky.
   * *(3)* **Generátor Výrobního pasu rozváděče podle platné normy pro rozváděče nízkého napětí (výpočet oteplení podle platné metodiky + `CE`) + Elektronický stavební deník** s hlasovým diktováním z mobilu + bezkolizní kalendář zdrojů a trasy (`Mapy.cz` API — **vyžaduje komerční licenci a uvedení v Příloze 4**, případně vlastní `OSM/OSRM`).
   * *(4)* **Česko-slovenské jádro `cz-sk-registry-kernel`** — `ARES`, `ADIS` (ručení za DPH), `ISIR`, `CEE`, `RPO`, `RegisterUZ`, `ISDOC` / `Peppol` a připravenost na případnou zákonnou evidenci tržeb.
5. **Tarify bez příplatku za montéra + měřený rozpočet tokenů s tvrdým stropem na tenant:**
   * Předplatné se platí za celou elektro firmu (`Solo RT` / `Elektro Tým` / `Elektro Firma`), nikdy za hlavu montéra v terénu (s rozlišením kancelářských uživatelských účtů a parametrů *fair-use* v `tarify-saas.md`). Všechny ceny a číselné limity jsou v `tarify-saas.md` vedeny jako `NÁVRH — ke schválení 1001`.
   * Každý tenant má vlastní měřený rozpočet tokenů s tvrdým stropem; spotřeba tenantů se nikdy neúčtuje do interního stropu `470 USD / měsíc` a naopak. Interní strop `470 USD` a počet `20` `ai` zaměstnanců se Blokem 19 nemění.
6. **`Liability Firewall` — `ai` generuje jen `DRAFT`:**
   * Polarita Elektro Cloud dodává softwarový a deterministický výpočetní nástroj. Každý výstup `ai` je koncept (`DRAFT`); odbornou, normovou a zákonnou odpovědnost za vydanou revizní zprávu, Výrobní pas či prohlášení o shodě nese vždy podepisující revizní technik / zhotovitel zákazníka s vlastním Oprávněním TIČR.
   * Platforma nikdy nepodepisuje za zákazníka a nikdy nevydává dokument bez výslovného úkonu jeho oprávněné osoby. Plné znění článků je v `licencni-podminky-osnova.md` (k revizi `15001` a advokátem).
7. **Role podle GDPR:**
   * Zákazník je **správcem** osobních údajů svých klientů, zaměstnanců a partnerů; Polarita s.r.o. je **zpracovatelem** a zpracovává je pouze podle pokynů zákazníka na základě zpracovatelské smlouvy podle GDPR, která je přílohou licenčních podmínek.
   * Další zpracovatelé (například poskytovatelé jazykových modelů a hostingu) musí být před spuštěním vyjmenováni v příloze smlouvy; dokud seznam není schválen `1001` a advokátem, pilotní tenant se nezakládá.

---

## 3. Pokyny pro `ai` (Prompty)

### Prompt 1 — Připravenost a měření brány `Go / No-Go` (`pro 11001 ceo` + `17005 ai-provoz`)

```text
Jsi 11001 ceo ve spolupráci s 17005 ai-provoz. Připrav pro 1001 koncept (DRAFT) protokolu brány Go / No-Go Strategické Etapy III podle balicky/S7-polarita-elektro-cloud/go-no-go-gate.md:

1. Zajisti změření pěti kritérií ze systémů polarita-hq (jen agregované počty, žádné osobní údaje). Každé kritérium měří ai zaměstnanec ze sloupce „Data připraví“ tabulky v go-no-go-gate.md; ty měření zadáváš, sbíráš a skládáš do protokolu:
   - délka bezchybného interního provozu od 12/12 PASS Go-Live Gate (protokoly Bloku 12, historie incidentů v Checkmk, protokoly testů obnovy a Full DR Drill),
   - počet aktivně spravovaných objektů v Digitální knize objektu (centralni-lhutnik-a-objekty),
   - počet vydaných revizních zpráv a Výrobních pasů rozváděčů (podepsané dokumenty v legal-archive, ne koncepty),
   - historie výsledků Eval Suite (balicky/S2-eval-suite a /srv/polarita/workspace/ai-finops/eval-suite/),
   - počet aktivních Certified Partner SUB (Partnerský provizní ledger a portal-spolupracovniku).
2. Ke každé hodnotě uveď zdroj, datum měření a dotaz nebo postup, kterým ji lze zopakovat. Nic neodhaduj; chybí-li zdroj, napiš NEZMĚŘENO.
3. Předej každé měření nezávislé kontrole ai zaměstnanci ze sloupce „Nezávisle potvrzuje“ téže tabulky (nikdy tomu, kdo hodnotu měřil). Stav přípravy konceptů licenčních podmínek a zpracovatelské smlouvy doplní 15001 pravni-specialista jen jako informaci k doplňkovým podmínkám.
4. Vyplň koncept protokolu. Verdikt GO navrhni pouze tehdy, když je splněno všech pět kritérií; jinak navrhni NO-GO a vypiš, co chybí.
5. Vlož koncept do Decisions. Rozhodnutí patří výhradně 1001; do jeho podpisu nespouštěj žádný krok Bloku 19.
```

### Prompt 2 — Multi-tenant jádro a `Row-Level Security` (`pro 17001 programator`, `17003 spravce-site` a `17004 klicnik`)

```text
Tento prompt smí být spuštěn až po podpisu GO v protokolu brány. Role: 17003 spravce-site staví klastr, 17001 programator datovou vrstvu, 17004 klicnik je Judge.

1. Oddělený produkční klastr (17003):
   - Postav samostatný klastr Incus + OpenTofu (0× Docker na hostiteli) bez jakéhokoliv síťového, databázového a klíčového spojení s polarita-hq. Vlastní PostgreSQL (latest), OpenBao (latest), Keycloak (latest), zálohy a monitoring.
   - Do klastru nepřenášej žádná data interního provozu Polarity.
2. Datová vrstva (17001):
   - Rozšiř metadata-schema-kernel tak, aby v primárním sdíleném schématu každé tabulce generoval složený klíč (tenant_id, id), ENABLE a FORCE ROW LEVEL SECURITY, omezující politiku AS RESTRICTIVE podle bezpečného current_tenant_id() a vlastní Clean Room pohledy (security_invoker = true); vyhrazené schéma ponech jen jako volitelnou nadstavbu. Vyjdi ze vzoru balicky/S7-polarita-elektro-cloud/rls-vzor.sql (vzor prošel na dočasné instanci PostgreSQL 18.7).
   - Aplikační role nesmí mít SUPERUSER ani BYPASSRLS. Kontext tenanta předávej pouze uvnitř transakce tokenem relace (app.tenant_token), který po ověření tokenu OIDC vydala autentizační brána vlastní rolí; aplikační role nesmí mít k tabulce tokenů žádné oprávnění a tenanta nikdy neuvádí přímo ani ze vstupu klienta. Omezující politiky vytvářej TO PUBLIC a funkci volej v politice skalárním poddotazem. Zápis do registru tenantů povol jen vyhrazené roli pro zakládání tenantů. V registru veď stav tenanta (aktivní / deaktivovaný s časem a odkazem na rozhodnutí) a ověřuj jej při vydání i při každém použití tokenu; každou změnou stavu zvyš generaci relací tenanta, aby deaktivace ve stejné transakci revokovala všechny dosud vydané relace a reaktivace je neobnovila. Expiraci tokenu porovnávej s časem začátku aktuálního příkazu, ne se začátkem transakce, a aplikační roli nastav limity délky příkazu a nečinné transakce výrazně pod životnost tokenu (dostupné parametry ověř proti oficiální dokumentaci nasazené verze PostgreSQL). Každé funkci SECURITY DEFINER připni search_path na výslovně povolenou hodnotu.
   - Pro každého tenanta založ vlastní šifrovací klíč v OpenBao.
3. Testy izolace (17001 píše, 17004 posuzuje):
   - Zařaď do Gitea Actions testy dokazující, že tenant A nevidí, nezmění ani nesmaže data tenanta B, že bez platného tokenu relace (chybějící, neplatný, neznámý, prošlý) dotaz vrátí 0 řádků, že token, který vyprší během otevřené transakce, přestane platit dalším příkazem, že deaktivovanému tenantovi se token nevydá a jeho dříve vydané tokeny neotevřou nic, zatímco ostatních tenantů se deaktivace netýká, že po reaktivaci staré tokeny dál neplatí a přístup otevře až nově vydaný token, že při skutečném přihlášení aplikační role (samostatná spojení, ne přepnutí role v jedné transakci) kontext tenanta nepřežije COMMIT ani ROLLBACK na znovu použitém spojení a další tenant na témže spojení vidí jen svá data — vyjdi z balicky/S7-polarita-elektro-cloud/rls-pool-test.sql (pracuje se zmenšenou kopií, izolaci skutečného schématu sám nedokládá; úlohu ber jako prošlou jen při návratovém kódu 0 a zároveň posledním řádku výstupu RLS_POOL_TEST_RESULT=PASS, chybějící nebo prázdné heslo_app úlohu shodí) a totéž ověř proti vygenerovanému schématu přes nasazený pooler, že se aplikační role nemůže prohlásit za jiného tenanta ani si vydat token, že každá tabulka má omezující politiku TO PUBLIC, že katalogová kontrola odmítne funkci SECURITY DEFINER bez search_path, jen s jiným parametrem i s nepovolenou hodnotou search_path, a že ai asistent jednoho tenanta nedostane kontext jiného.
   - Vydání do SaaS klastru zablokuj, pokud neprojde kterýkoliv test izolace, AigisCode nebo Eval Suite na 100 %.
4. Měření tokenů:
   - Zaveď měření spotřeby tokenů na tenant s tvrdým stropem; při dosažení stropu zastav jen ai funkce daného tenanta. Spotřebu tenantů nikdy neúčtuj do interního stropu 470 USD.
5. Výstup:
   - Protokol testů izolace ulož do dokumentace klastru a založ položku v Decisions. Nic nevydávej za nasazené, pokud to neproběhlo.
```

### Prompt 3 — Produktizace, licenční podmínky a onboarding prvního pilotního tenanta (`pro 11001 ceo`, `15001 pravni-specialista` a `17003 spravce-site`)

```text
Tento prompt smí být spuštěn až po podpisu GO a po prošlých testech izolace z Promptu 2. Před podpisem GO smějí v této složce vznikat jen koncepty (DRAFT) licenčních podmínek a návrhu tarifů; jejich revize advokátem a schválení 1001 jsou podmínkou založení pilotního tenanta, ne podmínkou GO.

1. Licenční a obchodní podmínky (15001 pravni-specialista):
   - Dopracuj koncept podle balicky/S7-polarita-elektro-cloud/licencni-podminky-osnova.md včetně článků Liability Firewall a rozdělení odpovědnosti a připrav zpracovatelskou smlouvu (zákazník = správce, Polarita s.r.o. = zpracovatel) se seznamem dalších zpracovatelů.
   - Výstup je DRAFT. Podmínky smí být použity až po revizi advokátem a schválení 1001.
2. Tarify (11001 ceo):
   - Připrav pro 1001 návrh hodnot do balicky/S7-polarita-elektro-cloud/tarify-saas.md. Každou cenu a limit doprovoď výpočtem nákladů; žádné číslo nezveřejňuj před mutation_confirm.
3. Výběr pilotního tenanta (11001 ceo):
   - Navrhni pilotního zákazníka z řad aktivních Certified Partner SUB. Výběr i smlouvu schvaluje 1001.
4. Onboarding (17003 spravce-site):
   - Po podpisu smlouvy založ tenanta: řádek v registru tenantů sdíleného schématu včetně stavu aktivní (vyhrazenou rolí pro zakládání tenantů; vyhrazené schéma jen u sjednaného enterprise nadstandardu), klíč v OpenBao, Clean Room, správce účtu zákazníka, logo a klientský portál. Ověř testem izolace, že nový tenant nevidí žádná cizí data.
   - Import dat zákazníka (například historické šanony) provádí zákazník nebo se provádí na jeho pokyn jako správce údajů; projde antivirem a karanténou stejně jako interně.
5. Ověření Liability Firewall v produktu:
   - Zkontroluj, že každý výstup ai je označen DRAFT, že revizní zprávu, Výrobní pas ani prohlášení o shodě nelze vydat bez úkonu oprávněné osoby zákazníka a že platforma nikdy nepodepisuje za zákazníka.
6. Výstup:
   - Souhrn pilotu vlož do Decisions: co je hotové, co neprošlo, co čeká na člověka.
```

---

## 4. Ověřitelné podmínky dokončení Bloku 19

- [ ] Protokol brány `Go / No-Go` má všech pět kritérií změřených se zdrojem a datem, verdikt `GO` a podpis `1001`; bez něj se žádná další podmínka neplní.
- [ ] SaaS klastr běží odděleně od `polarita-hq` (vlastní `Incus`, `PostgreSQL`, `OpenBao`, `Keycloak`, zálohy) a audit `17004` potvrdil `0` síťových, databázových a klíčových vazeb i `0` dat interního provozu Polarity v klastru.
- [ ] Každá tabulka tenantů ve sdíleném schématu má složený klíč `(tenant_id, id)`, `ENABLE` i `FORCE ROW LEVEL SECURITY` a politiku `AS RESTRICTIVE` vytvořenou `TO PUBLIC`, aplikační role nemá `BYPASSRLS`, nemůže si sama určit tenanta ani zapsat do registru tenantů a testy izolace (tenant A × tenant B, chybějící / neplatný / prošlý token relace = `0` řádků, token prošlý během otevřené transakce = `0` řádků, deaktivovaný tenant = žádný nový token a `0` řádků s dříve vydaným tokenem i po reaktivaci, skutečné přihlášení aplikační role a znovu použité spojení po `COMMIT` i `ROLLBACK` = `0` řádků bez nového tokenu, pokus o přímé uvedení cizího tenanta = `0` řádků, katalogová kontrola hodnoty `search_path` u funkcí `SECURITY DEFINER` včetně záporného testu, `Clean Room` pohled s `security_invoker = true`) procházejí v `Gitea Actions` při každém vydání.
- [ ] Každý tenant má vlastní šifrovací klíč v `OpenBao` a vlastní `Clean Room`; test prokázal, že `ai` asistent jednoho tenanta nedostane data jiného.
- [ ] Měřený rozpočet tokenů má tvrdý strop na tenant (test: po dosažení stropu se zastaví jen `ai` funkce daného tenanta) a tarify v `tarify-saas.md` jsou schváleny `1001`.
- [ ] Licenční podmínky s články `Liability Firewall` a zpracovatelská smlouva prošly revizí `15001` a advokátem a byly schváleny `1001`; v produktu nelze vydat dokument bez úkonu oprávněné osoby zákazníka.
- [ ] První pilotní tenant je založen na základě podepsané smlouvy a jeho onboarding je doložen protokolem v `Decisions`.

---

## 5. Stav ve Verzi 3.2.2

**Hotové v této složce (architektura, brána a vzory):**

- `README.md` — řídicí dokument Bloku 19 (seznam softwaru, pravidla, tři prompty, podmínky dokončení).
- `go-no-go-gate.md` — kritéria brány, zdroje měření a rozhodovací protokol s podpisem `1001`.
- `rls-vzor.sql` — vzor izolace tenantů v `PostgreSQL` (čtyři role, token relace s expirací posuzovanou po příkazech, stav deaktivace tenanta ověřovaný při vydání i použití tokenu, generace relací revokující staré relace při deaktivaci i reaktivaci, omezující politiky `TO PUBLIC`, izolační testy včetně katalogové kontroly hodnoty `search_path` se záporným testem a výčet známých mezí). **Kontroly vzoru prošly na dočasné instanci PostgreSQL 18.7. Před nasazením je zopakuj nad vygenerovaným schématem.**
- `rls-pool-test.sql` — doplňkový test pro `psql`: skutečné přihlášení aplikační role a jedno spojení použité pro další transakce po `COMMIT` i `ROLLBACK` (kontext tenanta nesmí přežít), ukázka úniku při nastavení tokenu na celou relaci. Vyžaduje samostatná spojení a instanci určenou k zahození, na rozdíl od `rls-vzor.sql` potvrzuje a po sobě uklízí. Pracuje se **zmenšenou kopií** vzoru (vlastní zjednodušený resolver a vlastník objektů), takže jeho průchod dokládá jen chování přihlášení a znovu použitého spojení na této kopii a **neprokazuje izolaci skutečného schématu**; ta se ověřuje stejnými zkouškami proti schématu vygenerovanému `metadata-schema-kernel` přes nasazený pooler. Podmínka průchodu pro `Gitea Actions`: návratový kód `psql` je `0` **a zároveň** poslední řádek standardního výstupu je přesně `RLS_POOL_TEST_RESULT=PASS`; chybějící nebo prázdná proměnná `heslo_app` i každá neprošlá kontrola končí nenulovým návratovým kódem, samotný kód `0` bez tohoto řádku se za průchod nepovažuje. **Na dočasné instanci PostgreSQL 18.7 vrátil skript stav 0 a výsledek RLS_POOL_TEST_RESULT=PASS.**
- `tarify-saas.md` — struktura tří tarifů; všechny ceny a číselné limity jsou `NÁVRH — ke schválení 1001`.
- `licencni-podminky-osnova.md` — osnova podmínek s plným zněním klíčových článků; koncept k revizi `15001` a advokátem, ne platný právní dokument.

**Podmíněno bránou `Go / No-Go` (neprovedeno):**

- Pořízení a stavba SaaS klastru, rozšíření `metadata-schema-kernel` o tenanty, měření tokenů, klientský portál a onboarding pilotního tenanta.
- Měření brány samotné — vyžaduje 12–18 měsíců ostrého provozu na serveru `polarita-hq`, který zatím neexistuje (greenfield návrh).

Polarita Elektro Cloud ve Verzi 3.2.2 **není spuštěn, nasazen ani nabízen zákazníkům**; neexistuje žádný tenant, klastr ani uzavřená smlouva. Blok 19 se spustí nejdříve po splnění brány a podpisu `1001`.
