# Blok 16 · Balíček S4 — Dotykový Dílenský terminál rozváděčů a Půjčovna měřidel · Verze 3.0

Tento dokument řídí **Blok 16** Rozvojové Etapy II společnosti **Polarita s.r.o.** (release `Polarita-3.0`). Balíček `S4` přidává dvě věci: dotykový kiosk `dilensky-terminal` pro kompletaci a kusové ověření rozváděčů na dílně centrálního skladu `MAIN-101` a modul `pujcovna-meridel` pro B2B pronájem měřidel, mobilních staveništních rozváděčů a elektrocentrál.

Blok 16 lze spustit až po `12/12 PASS` Go-Live Gate (Blok 12) a nezávisí na Blocích 13–15 ani 17–18. Navazuje na čtyři hotové vrstvy: **Blok 8** (`centralni-lhutnik-a-objekty` — bezkolizní kalendář zdrojů `N4`, Lhůtník kalibrací, `QR měřidla`), **Blok 9** (`elektro-wms` — registr `S/N`, `PHE`, blokace expedice rozváděče bez pasu), **Blok 10** (`cad-urs-engine` — kusovník, ověření návrhu, Výrobní pas rozváděče) a **Blok 11** (`portal-spolupracovniku` — zámek `ZPŮSOBILÝ: ANO/NE`, `finance-uol-marze-engine`, `cz-sk-registry-kernel`).

Balíček nezakládá žádného nového `ai` zaměstnance, žádné oddělení, žádnou novou databázi ani databázový stroj. Data výroby a půjčovny žijí v dedikovaných schématech `dilna` a `pujcovna` v `db_erp_lhutnik`, sdílená tabulka kalendáře zdrojů `resource_booking` ve stejné databázi, skeny `S/N` v nástavbových tabulkách `elektro-wms` v `db_eshop`; obojí vzniká z deklarativních schémat přes `metadata-schema-kernel`. Strop `470 USD / měsíc` se nemění.

---

## 1. Seznam softwaru a modulů

| Oblast | Vybraný software / modul | Kanál / Režim | Role a použití | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Dílenský kiosk kompletace rozváděčů** | Vlastní modul **`dilensky-terminal`** (PWA `Astro` + `TypeScript` + `Tailwind CSS` nad `elektro-wms` a `cad-urs-engine`) | `latest` *(open-source + vlastní kód `17001`; jen `app_internal` za Headscale VPN + Keycloak)* | Dotyková obrazovka na dílně `MAIN-101`: přihlášení pracovníka, `Start / Pauza / Stop` operace ke spisu `POL-RRRR-NNNNN`, sken `S/N` přístrojů do kusovníku, checklist kusového ověření. | `17001` `programator` / `17002` `webmaster` *(provoz `13001` `eshop`, kontrola `17004` `klicnik`)* |
| **Kusové ověření a vazba na Výrobní pas** | Rozšíření **`cad-urs-engine`** (`Python Decimal` + `Typst`) o protokol kusového ověření | `latest` *(vlastní kód `17001`)* | Kritéria bere z registru norem `15002`, protokol vkládá do pasu, připraví `DRAFT` EU prohlášení o shodě. Oteplení zůstává ověřením návrhu výpočtem podle platné metodiky. | `17001` `programator` / `14001` `projektant` *(Judge `15002` `normovac`, podpis `1001`)* |
| **Čtení kódů GS1 / QR** | USB čtečka v režimu klávesnice + čtení kamerou v PWA (`zxing-js`) + vlastní parser aplikačních identifikátorů GS1 | `latest` *(open-source, bez placených licencí)* | Čte `GS1 DataMatrix`, `GS1-128` a QR; vytěží GTIN, sériové číslo a šarži. Přístroj bez strojově čitelného `S/N` se zapíše ručně s fotografií štítku. | `17001` `programator` / `13001` `eshop` |
| **Tisk štítku CE a podkladu `PHE`** | **`Typst`** + **`qrcode / python-barcode`** + tisková fronta **`CUPS`** | `latest` *(open-source)* | Sazba výrobního štítku CE s QR do Digitální knihy objektu a podkladu pro recyklační příspěvek `PHE`. Tisk odemkne až server po splnění zámků z pravidla 6. | `17003` `spravce-site` / `13001` `eshop` |
| **Systém kiosku** | Ubuntu + prohlížeč `Chromium` v režimu kiosku, zařízení zapsané v Headscale | `latest LTS` / `latest` *(open-source)* | Uzamčená stanice bez přístupu k ploše a bez uložených tajemství; identitu zařízení a relace drží Keycloak, tajemství jen OpenBao. | `17003` `spravce-site` *(audit `17004` `klicnik`)* |
| **Půjčovna a rezervace** | Vlastní modul **`pujcovna-meridel`** (rozšíření kalendáře zdrojů v `centralni-lhutnik-a-objekty`) | `latest` *(vlastní kód `17001`)* | B2B pronájem analyzátorů sítí, termokamer, testerů EV nabíječek, mobilních staveništních rozváděčů a elektrocentrál; rezervace bez kolize s interními výjezdy. | `14005` `zakazky` / `17001` `programator` *(kontrola `15001` `pravni-specialista`)* |
| **Předávací protokol, kauce a fakturace** | PWA **`portal-spolupracovniku`** (foto do `Garage`, pečeť `pyHanko`) + **`finance-uol-marze-engine`** | `latest` *(vlastní kód `17001` / `17002`)* | Digitální protokol předání a vrácení s fotodokumentací, evidence kauce, `DRAFT` faktury za pronájem. | `16001` `ucetni` / `14005` `zakazky` *(schválení `1001`)* |

---

## 2. Architektonická pravidla

1. **Kiosk běží jen ve vnitřní síti a nezná osobní údaje:**
   * `dilensky-terminal` je nasazen v zóně `app_internal`, dostupný výhradně přes Headscale VPN a Keycloak OIDC; z internetu ani z `dmz_edge` dosažitelný není.
   * Pracovník se přihlásí QR kódem nebo čipem. Nosič nese jen náhodný neprůhledný identifikátor, který Keycloak převede na osobní číslo `1001+`; jméno ani jiné PII se do schémat `dilna` a `pujcovna` neukládá.
2. **Každá operace patří ke spisu a k osobě:** tlačítka `Start / Pauza / Stop` (dotykem nebo pípnutím čtečky) zapisují neměnné události ke konkrétnímu rozváděči a spisu `POL-RRRR-NNNNN`; jedna osoba má v jednu chvíli spuštěnou nejvýše jednu operaci. Časy slouží k post-kalkulaci zakázky, ne k automatickému hodnocení osob, a pracovník musí mít předem v `portal-spolupracovniku` evidované seznámení vyžadované pravidly pro sledování zaměstnanců podle pracovněprávních předpisů.
3. **`S/N` jističů a chráničů se skenuje přímo do kusovníku:** sken se páruje s řádkem kusovníku z `cad-urs-engine` a se skladovou položkou a B2B zárukou v `elektro-wms`. Přístroj, který v kusovníku není, nebo `S/N` už použité v jiném rozváděči kiosk odmítne.
4. **Kusové ověření podle platné normy pro rozváděče nízkého napětí je povinný checklist, ne volný text:**
   * Checklist má devět bodů (viz [kusove-overeni-checklist.md](./kusove-overeni-checklist.md)); kritéria a mezní hodnoty se načítají z normové báze ve Vaultu (`03-Normy-a-Metodiky/`), kterou vede `15002 normovac`, nikdy z paměti `ai`.
   * **Oteplení není bod kusové zkoušky.** Je to ověření návrhu výpočtem podle platné metodiky z `cad-urs-engine`; kiosk jen kontroluje, že toto ověření u rozváděče existuje. Zadání `S4` v zásobníku jej uvádí mezi body kusové zkoušky — zde je to opraveno.
5. **`Hard-Stop` na kalibraci a způsobilost:** bez platné kalibrace každého použitého měřidla v den zkoušky (Lhůtník) nebo bez stavu `ZPŮSOBILÝ: ANO` u osoby, která ověření provádí, nelze kusové ověření uzavřít. U bodů 3 a 8 checklistu kiosk nedovolí zvolit způsob bez měřidla a výrok `NEPOUŽIJE SE` nabídne jen tam, kde jej pro daný typ výrobku připouští registr `15002`. Zámky drží i databázová omezení ve schématu, ne jen kód kiosku. Uzavřít ani tisknout nelze ani z offline fronty — tyto kroky vždy vyhodnocuje server.
6. **Štítek CE a podklad `PHE` se tisknou až po `VYHOVUJE` a vydaném pasu:** tisk odemkne celkový výrok `VYHOVUJE`, vygenerovaný Výrobní pas a podepsané EU prohlášení o shodě. Při `NEVYHOVUJE` se štítek netiskne, závady se zapíší a rozváděč se vrací do kompletace; nové ověření je nový záznam, starý se nepřepisuje. Zneplatní-li `1001` později už uzavřené ověření, odvolá se prohlášení o shodě, zneplatní se pas i vytištěné štítky a rozváděč se vrací do ověření z kteréhokoli stavu včetně `RELEASED` (po fyzickém návratu na dílnu a obnovení blokace expedice v `elektro-wms`).
7. **Prohlášení o shodě podepisuje člověk:** `ai` připraví jen `DRAFT` EU prohlášení o shodě podle předpisů o posuzování shody elektrických zařízení nízkého napětí; po kontrole `15002 normovac` jej v `Decisions` potvrdí (`mutation_confirm`) a osobním kvalifikovaným podpisem podepíše `1001`. Výrobní číslo přiděluje atomicky `cz-sk-registry-kernel`.
8. **Půjčovna je B2B a jen pro prověřené nájemce:**
   * Půjčují se analyzátory sítí, termokamery, testery EV nabíječek, mobilní staveništní rozváděče a elektrocentrály — pouze `Certified Partner SUB` a B2B zákazníkům schváleným `1001` v `Decisions`.
   * Zdroj smí opustit sklad jen s platnou kalibrací (u zdrojů a rozváděčů s platnou revizí / kontrolou) vedenou v Lhůtníku po celou dobu výpůjčky, s přijatou kaucí (nebo se zapsaným rozhodnutím `1001` v `Decisions`, že se kauce nevybírá) a s podepsaným digitálním předávacím protokolem s fotodokumentací (vzor: [predavaci-protokol-pujcovna.md](./predavaci-protokol-pujcovna.md)).
9. **Rezervace jsou bezkolizní a interní revizní výjezd má přednost:** půjčovní i interní rezervace a servisní okna sdílejí jednu tabulku kalendáře zdrojů `resource_booking` v `db_erp_lhutnik` s databázovým vylučovacím omezením (zdroj + časový interval), takže se tentýž zdroj nemůže překrýt ani při souběžných zápisech. Termín se drží už od žádosti a interní výjezd bez vlastní potvrzené rezervace zdroj ze skladu nevydá. Stav výpůjčky, její rezervace v kalendáři a půjčeného zdroje se nikdy nemění jeden po druhém: každá společná změna je jedna atomická operace, která nejdřív ověří podmínky nad stavem před změnou, pak zapíše všechny nové stavy a nakonec ověří přípustnou kombinaci stavů — jinak se nezapíše nic. Nepotvrzenou půjčovní žádost interní revizní výjezd vytlačí; potvrzená výpůjčka se nikdy neruší automaticky — střet jde k `1001` do `Decisions`.
10. **Fakturace a ceník:** pronájem fakturuje `finance-uol-marze-engine` z podkladu schváleného v `Decisions`; vrácení i zadržení kauce potvrzuje `1001`. Fakturuje se podle ceníku zafixovaného při potvrzení výpůjčky. Ztráta nebo nevrácení zdroje se vede jako škoda bez vratného protokolu a rozhoduje o ní `1001`. Zdroj se nevratně odepisuje až při uzavření případu ztráty, ve stejné operaci jako uzavření výpůjčky; do té doby zůstává vedený jako půjčený a pozdní vrácení je možné jen auditovanou cestou — s vratným protokolem, potvrzením `1001` a přejímkou zdroje jako při každém jiném vrácení. Ceník půjčovny, výše kaucí, minimální počet fotografií a požadovaný stupeň kvalifikace pro kusové ověření jsou **`NÁVRH — ke schválení 1001`**; tento balíček neobsahuje žádné částky a bez schváleného ceníku nelze výpůjčku potvrdit.

---

## 3. Pokyny pro `ai` (Prompty)

### Prompt 1 — Datový model a kiosk `dilensky-terminal` (`pro 17001 programator` + `13001 eshop`)

```text
Jsi hlavní vývojář (17001 programator) ve spolupráci s 13001 eshop, který provozuje sklad MAIN-101 a modul elektro-wms. Po 12/12 PASS Go-Live Gate vyviň modul dilensky-terminal: dotykovou PWA v režimu kiosku pro dílnu kompletace rozváděčů. Nezakládej nového agenta, novou databázi ani nový databázový stroj.

1. Datový model. Vezmi návrh schemata/dilensky-terminal.yaml z této složky, porovnej jej se skutečným formátem metadata-schema-kernel a vygeneruj migraci s rollbackem, OpenAPI endpoint s ETag, formulář a typovaný MCP nástroj. Entity výroby a ověření patří do schématu dilna v db_erp_lhutnik, sken S/N do nástavbových tabulek elektro-wms v db_eshop. Do vendor tabulek MedusaJS nezasahuj a vazbu mezi databázemi řeš přes API modulů, ne cizím klíčem.
2. Identita. Každý záznam nese case_id ve tvaru POL-RRRR-NNNNN a osobní číslo 1001–9999. Jméno ani jiné PII do těchto schémat neukládej. Přihlášení QR kódem nebo čipem řeš přes Keycloak: nosič obsahuje jen náhodný identifikátor, relace je krátká a po nečinnosti končí.
3. Nasazení. PWA (Astro + TypeScript + Tailwind CSS) nasaď v Incus kontejneru v zóně app_internal, dostupnou jen přes Headscale VPN a Keycloak OIDC. Tajemství drž výhradně v OpenBao.
4. Operace. Tlačítka Start, Pauza a Stop zapisují neměnné události k rozváděči a spisu. Před spuštěním ověř přes Clean Room pohled portal-spolupracovniku stav ZPŮSOBILÝ: ANO a evidenci seznámení vyžadovaného pravidly pro sledování zaměstnanců podle pracovněprávních předpisů. Jedna osoba smí mít spuštěnou jen jednu operaci. Při výpadku sítě ukládej Start, Pauza a Stop do místní fronty; uzavření ověření a tisk bez spojení se serverem nepovol.
5. Sken S/N. Čti GS1 DataMatrix, GS1-128 a QR z USB čtečky i kamery, vytěž GTIN, sériové číslo a šarži a spáruj je s řádkem kusovníku z cad-urs-engine a s položkou a B2B zárukou v elektro-wms. Přístroj mimo kusovník a S/N použité v jiném rozváděči odmítni. Bez strojově čitelného S/N povol ruční zápis s fotografií štítku.
6. Testy a předání. Pokryj stavové přechody, zámky a parser GS1 automatickými testy v Gitea CI (gitleaks, AigisCode). Výsledek předej ke kontrole 17004 klicnik (síťová zóna, Keycloak, OpenBao, 0 PII) a 15002 normovac (soulad modelu s kusovým ověřením). Nasazení vlož jako DRAFT s transakčním diffem do Decisions; proběhne až po mutation_confirm od 1001.
```

### Prompt 2 — Kusové ověření, tisk štítku CE / `PHE` a vazba na Výrobní pas (`pro 17001 programator` + `14001 projektant`, Judge `15002 normovac`)

```text
Jsi hlavní vývojář (17001 programator) ve spolupráci s 14001 projektant. Rozšiř cad-urs-engine a dilensky-terminal o kusové ověření rozváděče podle platné normy pro rozváděče nízkého napětí, vazbu na Výrobní pas a tisk štítků. Žádnou mez ani číslo článku normy nepiš zpaměti.

1. Checklist. Převeď kusove-overeni-checklist.md z této složky na povinný formulář kiosku s devíti body. Kritérium každého bodu načítej z normové báze ve Vaultu (`03-Normy-a-Metodiky/`), kterou vede 15002 normovac, a ulož verzi báze k záznamu. Naměřené hodnoty zpracuj v Python Decimal.
2. Oteplení. Oteplení nezařazuj mezi body kusového ověření. Před otevřením ověření jen zkontroluj, že u rozváděče existuje ověření návrhu s výpočtem oteplení podle platné metodiky z cad-urs-engine. Když chybí, ověření neotevři.
3. Zámky. Uzavření ověření zablokuj, pokud některé použité měřidlo nemá v den zkoušky platnou kalibraci v Lhůtníku, pokud osoba nemá stav ZPŮSOBILÝ: ANO, nebo pokud některý bod nemá výrok. U bodů 3 a 8 nepřipusť způsob bez měřidla; výrok NEPOUŽIJE SE nabídni jen tam, kde jej pro daný typ výrobku připouští registr 15002. Zámky vyhodnocuj na serveru, ne v prohlížeči kiosku, a přenes do migrace i databázová omezení ze schématu.
4. Výrok. Při VYHOVUJE vlož protokol kusového ověření do Výrobního pasu, vyžádej výrobní číslo z cz-sk-registry-kernel a vysázej v Typst návrh EU prohlášení o shodě jako DRAFT. Při NEVYHOVUJE zapiš závady, štítek netiskni a vrať rozváděč do kompletace; opakované ověření založ jako nový záznam.
5. Tisk. Tiskovou úlohu štítku CE s QR a podkladu PHE odemkni až po výroku VYHOVUJE, vydaném pasu a prohlášení o shodě podepsaném osobou 1001. Opakovaný tisk povol jen s důvodem a potvrzením v Decisions. Po tisku uvolni blokaci expedice v elektro-wms. Zneplatnění už uzavřeného ověření (jen s potvrzením 1001) musí odvolat prohlášení o shodě, zneplatnit pas a tiskové úlohy, obnovit blokaci expedice a vrátit rozváděč do ověření z kteréhokoli stavu; pokryj to testem.
6. Předání. Protokol, pas a DRAFT prohlášení předej ke kontrole Judge 15002 normovac v čistém kontextu a zabezpečení tisku ke kontrole 17004 klicnik. Prohlášení o shodě vlož do Decisions; podepisuje jej člověk 1001 osobním kvalifikovaným podpisem po mutation_confirm. Ty podpis nikdy nevytváříš ani nenapodobuješ.
```

### Prompt 3 — Půjčovna a rezervace `pujcovna-meridel` (`pro 17001 programator` + `14005 zakazky` + `16001 ucetni`)

```text
Jsi hlavní vývojář (17001 programator) ve spolupráci s 14005 zakazky (kalendář zdrojů) a 16001 ucetni (fakturace). Rozšiř bezkolizní kalendář zdrojů v centralni-lhutnik-a-objekty o modul pujcovna-meridel pro B2B pronájem. Žádnou cenu, sazbu ani výši kauce nevymýšlej.

1. Datový model. Vezmi návrh schemata/pujcovna.yaml, porovnej jej se skutečným formátem metadata-schema-kernel a vygeneruj migraci do schématu pujcovna v db_erp_lhutnik. Půjčovní i interní rezervace a servisní okna veď v jedné tabulce kalendáře resource_booking s vylučovacím omezením (zdroj + časový interval), aby pravidlo bez překryvu platilo na jednom místě a v databázi. Pokud Blok 8 tabulku kalendáře už založil, rozšiř ji migrací a druhou nezakládej. Potřebné rozšíření PostgreSQL ověř proti oficiální dokumentaci nasazené verze.
2. Nájemci. Výpůjčku povol jen nájemci typu Certified Partner SUB nebo B2B zákazník ve stavu APPROVED, kterého schválil 1001 v Decisions. Kontaktní osoby neukládej do schématu pujcovna; do protokolu se doplní až při sazbě PDF.
3. Rezervace. Termín zapiš do kalendáře už při žádosti (držená rezervace) a při potvrzení ji jen přepni. Společné změny stavu výpůjčky, její rezervace v kalendáři a zdroje implementuj jako atomické operace podle oddílu atomic_operations schématu (podmínky nad stavem před operací, zápis všech stavů, kontrola přípustné kombinace) a členské přechody nenabízej samostatně; před žádostí i před potvrzením ověř platnost kalibrace nebo revize v Lhůtníku až do plánovaného vrácení. Interní revizní výjezd má přednost: nepotvrzenou žádost vytlačí, střet s potvrzenou výpůjčkou pošli k 1001 do Decisions a nic neruš automaticky.
4. Protokol. Podle predavaci-protokol-pujcovna.md vytvoř v portal-spolupracovniku digitální protokol předání a vrácení: stav, příslušenství, fotografie do Garage, otisk kalibrace z Lhůtníku, kauce, podpisy obou stran, sazba v Typst a serverová pečeť pyHanko. Předání a vrácení jsou dva samostatně pečetěné záznamy. Bez zapečetěného protokolu předání a bez přijaté kauce (nebo zapsaného rozhodnutí 1001, že se kauce nevybírá) zdroj ze skladu nevydávej. Opravu zapečetěného protokolu řeš náhradním protokolem, nikdy úpravou; náhrada musí patřit ke stejné výpůjčce a mít stejný směr jako původní protokol a databáze to vynucuje složeným cizím klíčem.
5. Peníze. Ceník veď ve stavu NÁVRH, dokud jej 1001 neschválí; bez schváleného ceníku výpůjčku nepotvrzuj. Po vrácení připrav podklad k fakturaci a předej jej do finance-uol-marze-engine jako DRAFT. Vrácení i zadržení kauce a každou škodu včetně ztráty nebo nevrácení zdroje vlož do Decisions. Ztracený zdroj odepiš až při uzavření případu ztráty ve stejné operaci s uzavřením výpůjčky; pozdní vrácení přijmi jen s vratným protokolem, potvrzením 1001 a přejímkou zdroje a zapiš je do auditní stopy.
6. Předání. Výsledek předej ke kontrole 17004 klicnik (0 PII, přístupy, pečeť) a 15002 normovac (požadavky na kalibrace a revize půjčovaných zdrojů); návrh podmínek půjčovny posoudí 15001 pravni-specialista. Spuštění půjčovny, ceník a podmínky schvaluje 1001 v Decisions přes mutation_confirm.
```

---

## 4. Ověřitelné podmínky dokončení Bloku 16

- [ ] Kiosk `dilensky-terminal` je dosažitelný jen z `app_internal` přes Headscale VPN a Keycloak a pokus o přístup z internetu skončí odmítnutím.
- [ ] Testovací pracovník se přihlásí QR kódem nebo čipem a operace `Start / Pauza / Stop` se zapíší ke spisu `POL-RRRR-NNNNN` a osobnímu číslu, přičemž schémata `dilna` a `pujcovna` neobsahují žádné PII.
- [ ] Sken `S/N` jističe se zapíše do kusovníku a tentýž `S/N` nelze zapsat do druhého rozváděče.
- [ ] Kusové ověření nelze uzavřít s měřidlem s propadlou kalibrací ani osobou ve stavu `ZPŮSOBILÝ: NE` (oba testy vrací `Hard-Stop`).
- [ ] Štítek CE a podklad `PHE` nelze vytisknout před výrokem `VYHOVUJE`, vydaným pasem a prohlášením o shodě podepsaným `1001`; při `NEVYHOVUJE` zůstává tisk zablokován.
- [ ] Půjčovní rezervaci nelze založit do termínu obsazeného interním výjezdem ani na zdroj, jehož kalibrace nebo revize skončí před plánovaným vrácením.
- [ ] Zkouška prokázala, že stav výpůjčky, rezervace v kalendáři a zdroje nelze změnit jednotlivě (potvrzení, zrušení, předání, vrácení i uzavření projdou jen jako celá operace), že ztracený zdroj nelze odepsat před uzavřením případu ztráty, že pozdní vrácení vede zdroj do přejímky a že náhradní protokol nelze založit k jiné výpůjčce ani k jinému směru.
- [ ] Zkušební výpůjčka projde celým cyklem (potvrzení `1001`, kauce, protokol předání a vrácení s fotografiemi, `DRAFT` faktury ve `finance-uol-marze-engine`) a kontroly `15002 normovac` a `17004 klicnik` mají výsledek `PASS`.

---

## 5. Stav ve Verzi 3.0

**Hotovo v této složce (dokumentace a návrhy):**

- `README.md` — tento řídicí dokument se třemi prompty.
- `schemata/dilensky-terminal.yaml` a `schemata/pujcovna.yaml` — návrh deklarativních schémat (entity, pole, vazby, stavy, přechody, pole povinná pro uzavření). Oba soubory jdou načíst jako YAML a prošly strojovou kontrolou vnitřní konzistence (každý stav je dosažitelný, každý nekoncový stav má výstup, koncové stavy jsou vyjmenované, každý zámek je definovaný a použitý, odkazy mezi entitami míří na existující pole; u půjčovny navíc každá atomická operace odkazuje na existující přechody a její výsledek odpovídá vyjmenovaným přípustným kombinacím stavů výpůjčky, rezervace v kalendáři a zdroje). Kontrola neověřuje, že omezení jdou vytvořit v `PostgreSQL` — to prokáže až migrace při stavbě Bloku 16; formát je návrh a skutečné DSL `metadata-schema-kernel` určí `17001` při implementaci.
- `kusove-overeni-checklist.md` — checklist kusového ověření bez čísel článků a mezních hodnot; ty doplní registr `15002`.
- `predavaci-protokol-pujcovna.md` — vzor digitálního protokolu předání a vrácení s proměnnou `{{kauce}}`.

**Vyžaduje živý server `polarita-hq` (zatím neexistuje — nic z toho není nasazeno ani otestováno):**

- Vývoj, testy a nasazení PWA `dilensky-terminal` a modulu `pujcovna-meridel`, migrace schémat a rozšíření `cad-urs-engine`.
- Hardware: dotyková stanice kiosku, čtečka kódů, čtečka čipů a tiskárna štítků (výběr typů je `NÁVRH — ke schválení 1001`).
- Naplnění registru norem `15002` kritérii kusového ověření a ověření checklistu člověkem s odbornou kvalifikací.
- Rozhodnutí `1001`: ceník a kauce půjčovny, podmínky půjčovny (po posouzení `15001`), seznam zdrojů uvolněných k pronájmu, minimální fotodokumentace a požadovaná kvalifikace pro kusové ověření.
