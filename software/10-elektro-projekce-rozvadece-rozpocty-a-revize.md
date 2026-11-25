# 10 — Oborový elektro-inženýrský, CAD/BIM, výkopový (`DTM ČR`), rozpočtový a revizní software (`QElectroTech` + `LibreDWG / ezdxf / IfcOpenShell` + `cad-urs-engine` + volitelný pilot `CadCraft`) · Verze 3.28

Tento dokument definuje inženýrskou, projekční, rozpočtovou, revizní a produkční softwarovou vrstvu společnosti **Polarita s.r.o.** (v souladu s **Verzí 3.28** firemní struktury — oddělení `14` — `14001 projektant`, `14002 rozpoctar`, `14003 revizak`, `14004 skolitel`, ve spolupráci s `17001 programator`, `15002 normovac` a kreativními týmy `12` a `13`).

Architektura stojí na **produkčním průmyslovém open-source jádru `QElectroTech` (`.qet`) + `LibreDWG + ezdxf + IfcOpenShell + PyMuPDF` + `LibreCAD / FreeCAD / LibreOffice`** a **100% deterministickém elektrotechnickém, výkopovém (`DTM ČR`), výrobním (rozváděče nízkého napětí vč. výpočtu oteplení) a rozpočtovém jádru `cad-urs-engine`** (platné normy čte z normové báze vedené `15002 normovac`, tedy z registru platnosti norem, nikoli z tohoto návodu) napojeném na kontextová tlačítka **`„Pracuj“`** ve **360° Kartě spisu (`N2`)**, na **48h převzetí šanonů (`N7`)** i na **přepisy ústních víceprací z hovorů `Asterisk + WhisperX` (`#t=MM:SS` s příznakem `LEGAL_HOLD` přes `comm-gateway` — dopojení v `Bloku 11`)**, doplněném o samostatně ověřovanou pilotní AEC nadstavbu **`CadCraft` (`getcadcraft.com`, The Data Design Group, Inc., licence `Apache`)** — za `0 Kč` na licencích a plně funkční na **Windows**, **Linux**, **Apple macOS** i tabletech v terénu.

---

## 1. Seznam vybraného softwaru a modulů

| Oblast a agenda | Vybraný software / Stavební kámen | Kanál / Licence | Role a použití v Polarita s.r.o. (Verze 3.28) | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Vícepólová a jednopólová elektro schémata rozváděčů (produkční základ)** | **QElectroTech** *(formát `.qet` XML na stanicích `1001+` + export `.dxf` / `.pdf`)* | `latest` *(čistý open-source GPL, desktop Windows / Linux / macOS)* | Primární produkční elektrotechnický editor provozovaný interaktivně výhradně na pracovních stanicích `1001+` (nikoliv v hlavním hostitelském OS serveru) se značkami podle platné normy pro grafické značky ve schématech a křížovými odkazy jističů, chráničů a stykačů podle platné normy pro referenční označování. Formát `.qet` je čisté XML — `14001 projektant` (`cad-urs-engine`) jej na serveru strojově generuje a člověk jej upraví na své stanici; případný headless převod `.qet -> PDF` na serveru běží jen v izolovaném kontejneru (`xvfb`), nikdy instalací GUI na hostiteli. | `14001` `projektant` *(kontrola Judge `15002` `normovac`)* |
| **Průmyslový čtecí, konverzní a desktopový CAD/BIM motor (produkční jistota)** | **LibreDWG** + **ezdxf** + **IfcOpenShell** + **PyMuPDF** *(v `sandbox_airgap`)* + desktop **LibreCAD / FreeCAD** | `latest` *(čistý open-source)* | Produkční serverové čtení i generování složitých architektonických `.dwg`, `.dxf`, `.ifc` a vektorových `.pdf` (vč. mapových podkladů správců sítí `DTM ČR`) v bez-síťové karanténě a interaktivní desktopová editace výkresů na Windows, Linuxu i macOS. | `17001` `programator` / `14001` `projektant` |
| **Deterministické normové výpočty, brána `DTM ČR`, Pasy rozváděčů (CE), rozpočty `.xc4` a revize (`F03`, `F04`)** | Vlastní modul **`cad-urs-engine`** (`Python Decimal` + `NumPy / SciPy / lxml / openpyxl` + **Typst**) | `latest` *(čistý open-source + vlastní kód `17001`)* | Neomylné matematické jádro firmy volané i z tlačítek **`„Pracuj“`**: výpočty $\Delta U$, $Z_s$, $I_k$, DLM, LPS, kontrola výkopů podle **platné normy pro prostorové uspořádání sítí technického vybavení (`DTM ČR`)**, **Výrobní pas rozváděče podle platné normy pro rozváděče nízkého napětí a příslušných výrobkových norem (EU prohlášení o shodě podle předpisů o posuzování shody elektrických zařízení nízkého napětí) + výpočet oteplení podle platné metodiky + štítek CE + QR** (normy čte z normové báze vedené `15002 normovac`, tedy z registru platnosti norem, nikoli z návodu), rozpočty a **Změnové listy víceprací** `.xc4`/`.xlsx` (`#t=MM:SS` `LEGAL_HOLD`), sazba kladných i **negativních revizních zpráv (`NÁVRH — NESCHOPNO BEZPEČNÉHO PROVOZU`)** a `Read-Only` diagnostika **`OCPP`**. | `17001` `programator` *(Judge `15002` `normovac`, podpis `QES` `1001` / `SUB-1007`)* |
| **Volitelná pilotní AEC/BIM a odměřovací nadstavba v prohlížeči (`F14` — samostatný výrobce!)** | **CadCraft** + **BimCraft** + **TakeoffCraft** + **MarkupCraft** *(výrobce **The Data Design Group, Inc.**, `getcadcraft.com`)* | `latest` *(open-source licence `Apache`, Rust + WebAssembly — pilotně ověřovaná nadstavba)* | Volitelné webové/desktopové AEC nástroje od **The Data Design Group, Inc.** (`getcadcraft.com`): kalibrace měřítka a odměřování tras nad PDF (`TakeoffCraft`), červené zakreslování DSPS na tabletu (`MarkupCraft`) a prohlížení `.dxf`/`.ifc` (`CadCraft` / `BimCraft`). Nasazují se jako volitelný doplněk po praktickém ověření na vzorových elektro výkresech — nikdy jako jediné blokující jádro! | `14001` `projektant` / `14002` `rozpoctar` / terén `1001+` |
| **Kancelářské tabulky, PDF a oddělená kreativní produkce (`F14` — nesměšovat s `CadCraft`!)** | **LibreOffice** + **Typst** + kreativní nástroj **ArtCraft** *(`getartcraft.com` — výhradně grafika a vizuály oddělení `12` a `13`)* | `latest` *(open-source)* | Produkční tabulky a dokumenty běží v **`LibreOffice`** a **`Typst`**. Samostatný kreativní projekt **`ArtCraft` (`getartcraft.com`)** je odlišný produkt jiného výrobce než AEC sada `CadCraft` (`getcadcraft.com`) — v Polaritě slouží výhradně pro produktovou grafiku a vizuály marketingu/e-shopu (`12`, `13`), **nikdy ne jako CAD/BIM systém**. | `14002` `rozpoctar`, `12001` `marketing`, `12002` `obsah-geo`, `14004` `skolitel` |

---

## 2. Architektonická pravidla a zdůvodnění výběru

1. **Čisté oddělení produkčního CAD jádra, pilotní sady `CadCraft` (`getcadcraft.com`) a kreativního `ArtCraft` (`getartcraft.com`) (`F14`):**
   * Produkční inženýrský provoz Polarity stojí na průmyslově prověřených otevřených nástrojích **`QElectroTech`** (desktopový editor `.qet` na stanicích `1001+` + serverové generování XML `.qet` v `cad-urs-engine`), **`LibreDWG + ezdxf + IfcOpenShell + PyMuPDF`**, **`LibreCAD / FreeCAD`** a **`LibreOffice`**.
   * Sada **`CadCraft` (`getcadcraft.com` — `CadCraft`, `BimCraft`, `TakeoffCraft`, `MarkupCraft` od The Data Design Group, Inc., licence `Apache`)** je vedena jako odděleně ověřovaná volitelná AEC nadstavba nad otevřenými soubory `.dxf`, `.ifc` a `.pdf` a výslovně se nesměšuje s kreativním nástrojem **`ArtCraft` (`getartcraft.com`)**.
2. **Zákaz počítání elektrotechniky zpaměti, normová báze ve Vaultu (`F03`) a zákaz nočních samo-přepisů (Verze 3.28):**
   * Žádný `ai` agent nikdy neodhaduje průřez kabelu, zkratový proud, odstup inženýrských sítí, oteplení rozváděče ani součet rozpočtu v hlavě LLM — vždy volá deterministické funkce **`cad-urs-engine`**, jejichž výstup nezávisle přezkoumá v čistém kontextu **`Judge`** (`15002 normovac` / `14003 revizak`) na odlišné rodině modelu.
   * Nová výroba rozváděčů vychází z **platné normy pro rozváděče nízkého napětí** a výpočtu oteplení podle **platné metodiky**; `cad-urs-engine` je čte z normové báze, nikoli z návodu, a `15002 normovac` v ní udržuje přehled platnosti edic norem podle druhu výrobku, data a účelu (starší edice norem se použijí výhradně při posuzování historických rozváděčů podle data jejich uvedení do provozu). Žádný noční proces nesmí nikdy samočinně přepisovat výpočetní vzorce v `cad-urs-engine`.
3. **Přesné rozlišení blokace neúplných vstupů (`FAIL_CLOSED`) a generování negativní revizní zprávy (`F04`, `F18`):**
   * **Výkopový zámek `DTM ČR`:** U přípojek, zemničů LPS a sloupků EV wallboxů systém technicky zablokuje vydání realizační dokumentace k výkopu, dokud ve spisu `POL-RRRR-NNNNN` nejsou uložena platná *Vyjádření k existenci sítí* z **`DTM ČR`** a ověřené krytí/odstupy podle **platné normy pro prostorové uspořádání sítí technického vybavení**.
   * **`FAIL_CLOSED` při neúplných či nedůvěryhodných vstupech revize:** `cad-urs-engine` zablokuje vygenerování jakéhokoliv návrhu revizní zprávy, chybí-li platný kalibrační list měřidla v den měření, u nově osazeného rozváděče chybí Výrobní pas **rozváděče (CE + QR)** nebo chybí uzavřené listy Stavebního deníku / vytýčení `DTM ČR`.
   * **Povinné vygenerování návrhu negativní revizní zprávy při nevyhovujícím měření (`F04`):** Jsou-li vstupy i kalibrace úplné a platné, ale kterákoliv naměřená hodnota nevyhovuje limitu příslušné platné normy, generátor **technicky zablokuje kladný výrok `SCHOPNO BEZPEČNÉHO PROVOZU` i uvolnění díla k předání do provozu, ale povinně vygeneruje návrh negativní revizní zprávy (`NÁVRH — NESCHOPNO BEZPEČNÉHO PROVOZU`)** s přesným výčtem závad a lhůt pro posouzení a osobní kvalifikovaný podpis **`QES`** oprávněným lidským RT (`1001`, příp. aktivovaným zástupcem `SUB-1007` v režimu `Break-Glass`, který jedná **výhradně pod vlastním platným 5letým osobním `Osvědčením` revizního technika a vlastním 10letým podnikatelským `Oprávněním` TIČR** s pojistkou `>= 5 mil. Kč`).
4. **3úrovňová vzdálená diagnostika `OCPP` před výjezdem technika (`F24`):**
   * Při nahlášení závady chytrého EV wallboxu přes Servisní Helpdesk vyhodnotí inženýrská vrstva nejprve **`Read-Only` telemetrii `OCPP (latest)`**; vzdálený `Reset` smí proběhnout jen u zasmluvněného objektu po kontrole bezpečného stavu a souhlasu obsluhy a `UpdateFirmware` je vždy uzamčen za **`mutation_confirm`**, servisním oknem, podpisem image a rollbackem.

---

## 3. Pokyny k instalaci a vývoji modulů pro `ai` (Prompty)

**Zkouška při automatické instalaci.** Zpracuj vzorové výkresy a měření, ověř výstupní dokument i odmítnutí neúplných vstupů. Skutečný revizní podpis připojí oprávněná osoba po převzetí. Níže uvedené kroky s živou protistranou či osobním vybavením jsou součástí produkční aktivace po převzetí.


### Prompt 1 — Nasazení produkčního editoru `QElectroTech (latest)`, desktopového CAD základu a pilotního ověření `CadCraft` (`F14`) (`pro 17003 spravce-site` + `17001 programator`)

```text
V režimu TEST proveď průzkum, ulož plán a automaticky nasaď a ověř změny. Použij testovací data a místní protějšky externích služeb. Skutečné osobní klíče, certifikáty a živé účty zapoj až po uživatelském testu a převzetí správcem.
Jsi správce serveru (17003 spravce-site) ve spolupráci s hlavním vývojářem (17001 programator). Zprovozni pro inženýrský tým (oddělení 14) produkční elektrotechnický editor QElectroTech (latest) na pracovních stanicích 1001+, desktopové zálohy LibreCAD / FreeCAD / LibreOffice a oddělený pilotní kontejner pro sadu CadCraft (getcadcraft.com, Apache):

1. Produkční elektrotechnická schémata QElectroTech (latest) na stanicích 1001+ a desktopový CAD základ:
   - Připrav pro klientské pracovní stanice 1001+ (Windows, Linux, Apple macOS — nikdy v GUI na hlavním OS serveru) instalaci QElectroTech (latest, GPL) a založ ve složce /srv/polarita/workspace/inzenyring/projekce-cad/knihovna-qet/ verzovanou knihovnu značek podle platné normy pro grafické značky ve schématech a typových modulů rozváděčů (hlavní vypínače, chrániče typ A / B / A-EV, jističe, SPD T1/T2/T3, HDO, DLM řízení wallboxů) podle platné normy pro referenční označování; na serveru generuje cad-urs-engine čisté XML .qet a případný dávkový export PDF spouštěj jen v izolovaném jednorázovém kontejneru (xvfb).
   - Připrav multiplatformní instalační profily (Windows, Linux, Apple macOS) pro QElectroTech, LibreCAD, FreeCAD a LibreOffice.
2. Oddělené pilotní nasazení AEC sady CadCraft (getcadcraft.com, The Data Design Group, Inc., licence Apache) a kreativního ArtCraft (F14):
   - V zóně app_internal (za VPN Headscale + Keycloak SSO) připrav volitelný pilotní kontejner pro open-source AEC moduly CadCraft, BimCraft, TakeoffCraft a MarkupCraft z projektu getcadcraft.com (licence Apache): u každého modulu v záznamu přejímky samostatně ověř repozitář, licenci, skutečné rozhraní a funkčnost na reprezentativních elektro výkresech (.dxf, .ifc, .pdf).
   - Striktně v dokumentaci i konfiguraci odděl AEC sadu CadCraft (getcadcraft.com) od samostatného kreativního nástroje ArtCraft (getartcraft.com), který slouží výhradně pro grafiku a vizuály oddělení 12 a 13 a nikdy není označován za CAD/BIM software.
```

### Zkouška nativního schématu QElectroTech

Instalátor v `polarita-hq` ověří kontrolní součet vydání QElectroTech 0.100 a připraví zastavenou šablonu s virtuálním displejem. Pro zkoušku vytvoří dočasný kontejner bez sítě. V editoru pod běžným účtem otevře schéma 741, přes **Uložit jako** zapíše nový soubor a porovná polohu značek i propojené svorky na každém listu. Oba soubory a jejich SHA-256 uloží do důkazů bloku 10. [Instalační zkouška](../nasazeni/test/qet/schema.sh)

### Ověření měřítka PDF v pracovní VM

Do příjmu karantény vlož obsah souboru přes `prijem.py dxf`, `prijem.py dwg` nebo `prijem.py ifc`. Instalátor sestaví nástroje GNU LibreDWG 0.14 z archivu ověřeného podle SHA-256. Pro zkoušku DWG vytvoří binární vzor R2000 a po převodu změří poměr stran vykresleného obdélníku. Potvrzené ID propojuje originál, protokol antivirové kontroly i výsledný půdorys. Bezsíťový pracovník předá vykreslené PDF do Dangerzone a ověří, že z rekonstrukce vyšla pasivní rastrová kopie. Každé další měření svázané s tímto výstupem vyžaduje jeho vlastní SHA-256.

V bezsíťové pracovní VM poskytuje příkaz `polarita-cad-mereni vykres.pdf kalibrace.json` délku lomené trasy v milimetrech. Pro každou stranu připrav vlastní zadání. Uveď SHA-256 přesného souboru, číslo strany od jedničky, známé délky kót v milimetrech a souřadnice bodů v bodech PDF od levého horního rohu zobrazené strany. Při změně souboru proveď kalibraci znovu.

Instalátor vytvoří ve složce důkazů bloku 10 vzor `kalibrace.json` a jeho výsledek `mereni.json`. Alespoň dvě známé kóty musí mít různé směry. V režimu TEST je přípustný rozdíl měřítek nejvýše 1 % vůči nejmenšímu z nich. Chybějící nebo nesouhlasná kalibrace ukončí příkaz chybou `FAIL_CLOSED` před zveřejněním délky.

### Výkopová brána ve spisu

V ředitelství otevři **Spisy** a kartu projektu. Oddíl **Kontrola výkopů v TESTu** zobrazuje trasu a důvody případné blokace. Při stisku **Uvolnit v testu** systém znovu načte dnešní datum, revizi, metodiku a archivované přílohy daného spisu. Vyžaduje soupis sítí, platné souhlasné vyjádření každého správce a měření všech úseků. Krytí a odstup při křížení nebo souběhu porovnává v milimetrech s verzovanou zkušební metodikou. Při změně podkladů během zápisu vyžádá novou kontrolu.

Instalátor předá dva vzorové PDF dokumenty přes portál do karantény a Paperless. Technická zkouška používá výhradně smyšlené podklady a zkušební rozměry pro trasu R-TEST-01. Pro skutečný projekt stanoví pravidla normovač a podklady dodají příslušní správci sítí.

#### Nabídkový rozpočet v testovacím spisu

Instalátor ve VM `polarita-hq` vezme [modelový výkaz výměr](../nasazeni/test/inzenyring/rozpocet/vykaz-test.json), přepočítá položky na haléře a zapíše nabídku XC4 NZ. Před zpřístupněním obou souborů převede nabídku do Excelu a zpět, ověří ji proti schématu vydavatele a porovná výsledek s původním XC4. Správce otevře modelový spis a v oddílu **Nabídkový rozpočet** si stáhne oba formáty. [Datový předpis XC4 NZ](https://www.xc4.cz/podrobnosti/nz)

V listu **Položky** lze změnit množství, jednotkovou cenu a číselnou skupinu práce. List **Kontrola** ukazuje obsazení všech devíti skupin. Při zpětném převodu nástroj zachová strom stavby, ověří úplnost skupin a přepočítá celkovou cenu. Pro vydání nabídky se stejným identifikátorem musí zůstat zachovány všechny původní položky. Pro nový testovací výkaz lze dodat vlastní identifikátory i ceny. [Převodní nástroj](../nasazeni/test/inzenyring/rozpocet/rozpocet.py)

### Prompt 2 — Vývoj deterministického inženýrského, výkopového (`DTM ČR`) a rozpočtového jádra `cad-urs-engine` (normy z normové báze `15002 normovac` — `F03`) (`pro 17001`, `14001`, `14002` a Judge `15002`)

```text
V režimu TEST proveď průzkum, ulož plán a automaticky nasaď a ověř změny. Použij testovací data a místní protějšky externích služeb. Skutečné osobní klíče, certifikáty a živé účty zapoj až po uživatelském testu a převzetí správcem.
Jsi hlavní vývojář (17001 programator). Ve spolupráci s 14001 projektant, 14002 rozpoctar a pod kontrolou čistého kontextu Judge (15002 normovac) vyviň v jazyce Python (latest, Decimal) + Typst (latest) deterministický modul cad-urs-engine pokrytý jednotkovými testy (pytest):

1. Bez-síťový čtecí a kreslicí modul CAD/BIM + výkopová brána DTM ČR:
   - Integruj v sandbox_airgap (eth0 none; knihovny jsou součástí obrazu sestaveného v dočasné sestavovací instanci podle Bloku 2 a výkresy vstupují jediným tokem karanténa -> airgap-spool) knihovny LibreDWG (latest), ezdxf (latest), IfcOpenShell (latest) a PyMuPDF (latest) s povinnou kalibrací měřítka PDF na min. 2 nezávislé známé kóty (jinak FAIL_CLOSED).
   - Generuj výkresy .dxf se standardizovanými hladinami (včetně hladiny EL_VYKOPY_DTM_SITE pro ochranná pásma inženýrských sítí z DTM ČR) a u každé zemní trasy automaticky ověřuj minimální krytí a prostorové odstupy křížení/souběhu podle platné normy pro prostorové uspořádání sítí technického vybavení a přítomnost platných vyjádření správců sítí ve spisu POL-RRRR-NNNNN (chybí-li, vrať FAIL_CLOSED!).
2. Elektrotechnické výpočty nad normovou bází a Výrobní pas rozváděče (CE + QR):
   - Načítej normové konstanty z normové báze vedené 15002 normovac (řízený verzovaný registr platnosti norem podle druhu výrobku, data a účelu), nikoli z tohoto návodu, a naprogramuj deterministické výpočty: soudobý příkon, dimenzování vedení, úbytek napětí dU, impedanci smyčky Zs, zkratové proudy Ik, DLM bilanci nabíjení EV a analýzu rizika LPS.
   - Naprogramuj generátor kompletního Výrobního pasu nového rozváděče podle platné normy pro rozváděče nízkého napětí a příslušné výrobkové normy (obojí z normové báze) vč. návrhu EU prohlášení o shodě podle předpisů o posuzování shody elektrických zařízení nízkého napětí (s atomickým přidělením výrobního čísla z tabulky číselných řad založené v Bloku 5 (mutex SELECT ... FOR UPDATE v db_erp_lhutnik; v Bloku 11 ji se zachovaným stavem převezme cz-sk-registry-kernel)): výpočet oteplení podle platné metodiky, protokol ověření návrhu a kusového ověření, návrh EU prohlášení o shodě a tiskovou předlohu štítku CE + QR provázaného s Digitální knihou objektu. V CI pipeline Gitea technicky zakaž jakékoliv nehlídané noční samo-přepisy normových vzorců!
3. Modul stavebních rozpočtů (.xc4 XML a .xlsx) a 9 vrstev přípomocí:
   - Naprogramuj obousměrný parser a generátor formátu .xc4 i .xlsx s povinným checklistem 9 vrstev stavebních a zemních přípomocí (1 silnoproud a hromosvody, 2 slaboproud a DLM, 3 zemní práce vč. vytýčení sítí DTM ČR, 4 bourání, drážky a prostupy, 5 protipožární ucpávky EI, 6 zednické zapravení omítek, 7 příprava podkladu a malby, 8 inženýrská a revizní činnost, 9 VRN) a napojením na post-kalkulaci skutečné marže od 16001 ucetni (dopojení v Bloku 11).
```

### Prompt 3 — Modul kompletace kladných i negativních revizních zpráv (`F04`, `F18`) a 3úrovňové diagnostiky `OCPP (latest)` (`F24`) (`pro 17001 programator` + `14003 revizak`)

```text
V režimu TEST proveď průzkum, ulož plán a automaticky nasaď a ověř změny. Použij testovací data a místní protějšky externích služeb. Skutečné osobní klíče, certifikáty a živé účty zapoj až po uživatelském testu a převzetí správcem.
Rozšiř inženýrské jádro cad-urs-engine o deterministický modul přípravy kladných i negativních revizních zpráv a vyhodnocení vzdálené diagnostiky pro 14003 revizak se sazbou v systému Typst (latest):

1. Modulární import naměřených dat, 48h převzetí šanonů (N7), fotodokumentace a Read-Only OCPP telemetrie:
   - Vytvoř parser exportů z revizních měřicích přístrojů (CSV / XML / JSON), napojení na fotky zakrytých prací v Garage, normovou kontrolu vytěžených závad a expirací podle předpisů o vyhrazených elektrických zařízeních (lhůty revizí) u služby 48h digitálního převzetí šanonů (prevzeti-sanonu) a Read-Only čtení diagnostických logů chytrých EV wallboxů přes OCPP (latest) ze Servisního Helpdesku (vzdálený Reset povol jen u zasmluvněného objektu po kontrole bezpečného stavu a souhlasu obsluhy; UpdateFirmware vždy blokuj bez mutation_confirm v Decisions!).
2. Přesné oddělení blokace neúplných vstupů (FAIL_CLOSED) od návrhu negativní revizní zprávy (F04):
   - Zablokuj vygenerování jakéhokoliv návrhu revizní zprávy (FAIL_CLOSED), pokud jsou vstupy neúplné či nedůvěryhodné:
     a) u použitého měřidla chybí platný kalibrační list v den měření,
     b) u nově osazeného rozváděče chybí Výrobní pas rozváděče a štítek CE,
     c) u stavby podléhající deníku chybí uzavřené listy Elektronického stavebního deníku nebo u výkopu protokol vytýčení sítí DTM ČR.
   - Naopak pokud jsou vstupy a kalibrace úplné a platné, ale kterákoliv naměřená hodnota nevyhovuje limitu příslušné platné normy:
     d) TECHNICKY ZABLOKUJ kladný výrok „SCHOPNO BEZPEČNÉHO PROVOZU“ i uvolnění zakázky k předání do provozu, ale POVINNĚ VYGENERUJ návrh negativní revizní zprávy se závěrem „NÁVRH — NESCHOPNO BEZPEČNÉHO PROVOZU“, zvýrazněným soupisem zjištěných závad, porušených ustanovení norem a návrhem lhůt k odstranění pro lidského revizního technika!
3. Sazba a předání k osobnímu kvalifikovanému podpisu QES (F11, F18):
   - Vysázej v Typst (latest) návrh kladné či negativní revizní zprávy (PDF) a vlož jej s transakčním diffem (mutation_confirm) do Decisions k odbornému posouzení a osobnímu kvalifikovanému podpisu QES (JSignPdf na stanici RT s čipem QSCD) oprávněným lidským revizním technikem (1001 ve standardním provozu, příp. jmenovitě aktivovaným zástupcem SUB-1007 v režimu Break-Glass jednajícím pod vlastním 5letým osobním Osvědčením revizního technika a vlastním 10letým podnikatelským Oprávněním TIČR s pojistkou >= 5 mil. Kč + obchodním uvolněním v Decisions).
```

---

### Test kladné a záporné revizní zprávy

Instalátor založí dva samostatné spisy. Databáze přidělí modelovým rozváděčům samostatná výrobní čísla a zobrazí je v kartách spisů. Při opakování téhož požadavku zůstává číslo zachované. Generátor propojí podklady S1 s číslem konkrétního kusu a spisu. Oteplení vypočte interpolací zkušební křivky skříně při součtu ztrát osazených prvků. Chybná jednotka, neúplný kusovník, překročená teplota a výkon mimo rozsah křivky vystavení zastaví. Před zveřejněním PDF instalátor vyrastruje štítek, přečte QR a porovná jej s adresou digitální knihy objektu. Chráněný workflow Gitea porovnává otisky výpočtů a zkušebních metodik a kontroluje referenční výsledek oteplení. Všechny stránky jsou označeny TEST. Prohlášení pro skutečný výrobek vyžaduje platné normové podklady, odborné posouzení a podpis výrobce. V každém spisu instalátor zpřístupní návrh PDF a odkaz na posouzení v Decisions. Importy CSV, XML a JSON se kontrolují proti stejnému měřicímu plánu, kalibračnímu listu konkrétního přístroje a otiskům předepsaných podkladů. Cvičná metodika SIM-RZ-01 má modelové jednotky a mezní hodnoty určené pro ověření softwaru. V prvním spisu jsou výsledky přesně na obou mezích. Ve druhém jedna hodnota překročí maximum a zpráva uvede bod, obvod, ustanovení a návrh lhůty odstranění. Pokud chybí podklad, kontrola skončí před sazbou PDF. Obě varianty zůstávají uzavřené pro předání do provozu a čekají na odborné posouzení. [Vstupy a nástroje zkoušky](../nasazeni/test/inzenyring/revize/)

## 4. Ověřitelné podmínky dokončení Bloku 10

- [ ] Funguje produkční serverové generování `.qet` XML v `cad-urs-engine` i interaktivní desktopová editace elektro schémat rozváděčů v **`QElectroTech (latest)`** na stanicích `1001+` se značkami podle platné normy pro grafické značky ve schématech, doplněná o desktopový základ (`LibreCAD / FreeCAD / LibreOffice`) a samostatně zdokumentovaný volitelný pilot **`CadCraft`** (`getcadcraft.com`, `Apache`, striktně odlišený od kreativního `ArtCraft`).
- [ ] V bez-síťovém `sandbox_airgap` funguje čtení výkresů přes **`LibreDWG + ezdxf + IfcOpenShell + PyMuPDF`** s dvoubodovou kalibrací měřítka.
- [ ] Deterministický modul **`cad-urs-engine`** (`Python Decimal` + **`Typst latest`**) má `100 % PASS` v jednotkových testech (včetně scénáře **negativní revizní zprávy `NÁVRH — NESCHOPNO BEZPEČNÉHO PROVOZU`**) i u Judge (`15002`) na normové výpočty (normy z normové báze `15002 normovac`), **výkopovou bránu `DTM ČR`**, **Výrobní pasy rozváděčů podle platné normy pro rozváděče nízkého napětí (vč. výpočtu oteplení, CE + QR)** a rozpočty **`.xc4` / `.xlsx`**.
- [ ] Vzdálená diagnostika **`OCPP`** vynucuje 3úrovňové oddělení `Read-Only` čtení, podmíněného `Reset` a blokace `UpdateFirmware` bez `mutation_confirm`.
