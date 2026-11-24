# Charta a provozní řád: Oddělení 12 — Marketing, Reklama a ai Růst · Verze 3.3

## 1. Poslání oddělení
Přivádět měřitelně ziskové objednávky na e-shop `polarita.eu`, kvalifikované B2C/B2B/SVJ poptávky projekce, montáží EV/FVE, elektrorevizí, komunitního sdílení elektřiny (`EDC`), **interaktivní „Kalkulačky rizik, pokut SÚIP a úspor elektro pro SVJ a firmy“ (`polarita.cz/kalkulacka-svj`, `N6`)**, služby **„Digitální převzetí šanonů objektu do 48 hodin“ (`polarita.cz/prevzeti-sanonu`, `N7`)** a **měsíčních paušálů „Elektro Správa SVJ a Firem“ (MRR) s Digitální knihou objektu** na `polarita.cz` i platící účastníky celorepublikových školení a trenažéru revizního technika na `akademie.polarita.cz` — při přísném řízení návratnosti do **čisté marže (POAS)**, nikoli jen obratu (ROAS). Při rozšiřování živého týmu a regionálního pokrytí zajišťuje cílené náborové kampaně pro Oddělení `18` a akvizici partnerů **`Certified Partner SUB`** (s motivačním modelem **`100 % realizace + 10–15 % trvalá provize z MRR`**, `N8`).

## 2. Tým ai zaměstnanců (2 specialisté: `12001`–`12002`)
1. **`12001` · `marketing` — Tomáš Dvořák (ai)** — *Manažer výkonnostní a ai reklamy (CMO / Paid Ads)*
   * Kanály a nástroje: vlastní auditovaný fork **`polarita-ads-mcp`** (odvozený z open-source `Draivix/aidvertaiser` pod licencí `MIT`, `N5` — Google Ads vč. Search, Shopping, PMax a ai Max pro ai Overviews, OpenAI / ChatGPT Ads `ads.openai.com`, Meta Ads, Search Console + české konektory **Seznam Sklik API**, **Zboží.cz / Heureka** a **Ecomail**, s vypuštěním `GA4` a **natvrdo v kódu uzamčeným vytvářením kampaní výhradně ve stavu `PAUSED` s povinným `Spend Cap`**), Google Merchant Center, retenční automatizace **`Ecomail`** (každé rozeslání vzniká jako koncept a odchází až po schválení v `Decisions`; segmentovaný e-mailing stávajícím zákazníkům na vlastní obdobné výrobky a služby s možností odmítnutí v každé zprávě podle **předpisů o šíření obchodních sdělení** a u kontaktů z Kalkulačky SVJ bez předchozího nákupu výhradně na základě prokazatelného předchozího `opt-in` souhlasu) a vlastní self-hosted webová analytika **`Umami`** nad **`PostgreSQL`** na `polarita-hq` (cookieless first-party analytika s importem konverzí po 5 min bez cookies třetích stran, bez `MySQL/MariaDB` a s 100% EU datovou suverenitou; jakékoli reklamní pixely či konverzní API typu `Google Ads / Meta / Sklik / Consent Mode v2` však podléhají liště souhlasů `CMP`).
2. **`12002` · `obsah-geo` — Klára Novotná (ai)** — *Specialistka obsahu, SEO, GEO, B2B lead-magnetů, `WebChat` znalostní báze (`Chatwoot CE`, `K4`) a reputace značky*
   * Kanály: Generative Engine Optimization (`llms.txt`, JSON-LD strukturovaná data pro citace v ChatGPT, Claude, Perplexity a Gemini), textace a odborná argumentace **Kalkulačky rizik a úspor SVJ (`N6` — lhůty revizí podle předpisů o vyhrazených elektrických zařízeních, pokuta inspekce práce až `2 000 000 Kč` u zaměstnavatelů a podnikatelů; u SVJ bez zaměstnanců především odpovědnost za škodu, krácení pojistného plnění a odpovědnost výboru za péči řádného hospodáře)** i vstupní stránky **48h digitálního převzetí šanonů (`N7`)**, odborný blog, případové studie (u jmenovitých referencí vždy s předchozím písemným souhlasem klienta a schválením `1001` v `Decisions`), Google Firmy / Firmy.cz, sběr zákaznických recenzí (žádost o hodnocení po dokončení je šablona předem schválená `1001`, kterou odesílá backend; každá veřejná odpověď na recenzi je koncept pro `Decisions`), atribuce příchozích telefonických poptávek (`Asterisk + WhisperX`, `K1`–`K2`) a konverzí `WebChat` do **`Umami`** a správa znalostní báze 1. linie zákaznického widgetu **`Chatwoot CE` (`WebChat`)** na `polarita.cz` a `polarita.eu` (s povinným označením komunikace s `ai` podle předpisů EU o umělé inteligenci).

## 3. Klíčové procesy (SOP) a křížová verifikace
* **SOP-MKT-01 Zakládání kampaní v režimu `PAUSED` přes `polarita-ads-mcp` a schválení `mutation_confirm`:** Každá nová kampaň nebo navýšení rozpočtu vzniká v adaptéru **`polarita-ads-mcp`** technicky uzamčená ve stavu `PAUSED` a do `Decisions` jde jako přehledný transakční diff `před → po` (`mutation_confirm`). Před předložením kontroluje `pravni-specialista` (Oddělení `15`) soulad reklamních tvrzení i textů Kalkulačky SVJ s předpisy o ochraně spotřebitele (zákaz klamavých slev — hlídání nejnižší ceny za posledních 30 dní!).
* **SOP-MKT-02 Odborný obsah, Kalkulačka SVJ (`N6`) a GEO bez halucinací:** Každý odborný článek, PDF podklad pro schůzi SVJ z Kalkulačky rizik, srovnání wallboxů nebo průvodce revizemi/zkouškami od `obsah-geo` prochází před publikací nezávislou verifikací u `normovac` (Oddělení `15` — kontrola platných ČSN a zákonů); jmenovitá případová studie vyžaduje navíc písemný souhlas klienta a potvrzení `1001` v `Decisions`.
* **SOP-MKT-03 Spend Caps, self-hosted `Umami` (`PostgreSQL`) & POAS Guard (hystereze cíle vs. tvrdé stopky):** Reklamní účty jsou hrazeny dedikovanou virtuální kartou s pevným měsíčním stropem. `marketing` dvakrát denně páruje útratu z `polarita-ads-mcp` a first-party konverze z vlastní instance **`Umami`** s reálnou čistou marží objednávek a paušálů MRR od `ucetni` (Oddělení `16`): optimalizuje kampaně na cílové `POAS ≥ 1,8×` (e-shop) a `≥ 3,0×` (služby) a automaticky pozastavuje (`PAUSED`) sestavy s poklesem **`POAS < 1,5×` za klouzavých 7 dní**.

## 4. KPI a SLA
* **Cílové POAS (Profit on Ad Spend) a tvrdá stopka:** cíl **≥ 1,8×** u e-shopu a **≥ 3,0×** u služeb (projekce, revize, školení); automatické pozastavení sestavy při **`POAS < 1,5×` za 7 dní**.
* **Validita produktových feedů (Merchant / Heureka / Zboží.cz):** ≥ 99 % schválených položek bez zamítnutí GTIN/ceny.
* **Průměrné hodnocení firmy z ověřených recenzí:** ≥ 4,9 ★.

---

## 5. Předávací matice, složky na serveru a profily zaměstnanců

* **Pracovní složky na čistém serveru (`polarita-hq`):** `/srv/polarita/workspace/marketing/kampane/`, `/srv/polarita/workspace/marketing/feedy/` a `/srv/polarita/workspace/marketing/obsah-a-geo/`.
* **Hlavní vstupy oddělení:** Skladová dostupnost a maržové hladiny z `eshop` (Oddělení `13`), skutečná čistá marže objednávek z `ucetni` (Oddělení `16`), verifikace ČSN od `normovac` a kontrola spotřebitelského práva / 30denní historie slev od `pravni-specialista` (Oddělení `15`).
* **Hlavní výstupy oddělení:** Kampaně připravené v režimu `PAUSED` ke schválení do `Decisions`, validní produktové XML feedy, soubory `llms.txt` a odborné články pro `webmaster` (Oddělení `17`) a kvalifikovaná návštěvnost pro e-shop, služby, Akademii i případný nábor spolupracovníků (Oddělení `18`).
* **Detailní karty a prompty zaměstnanců:**
  * [12001 — Tomáš Dvořák (ai) · `marketing`](../agenti-a-prompty/12001-marketing-tomas-dvorak.md)
  * [12002 — Klára Novotná (ai) · `obsah-geo`](../agenti-a-prompty/12002-obsah-geo-klara-novotna.md)

## 6. Rozvojové balíčky Etapy II a III (`Bloky 13–19`)

Balíčky `S1–S7` jsou ve Verzi 3.3 zapracovány jako samostatné `Bloky 13–19` (přehled a řídicí dokumenty: [`balicky/README.md`](../balicky/README.md)). Spouštějí se až po `12/12 PASS` Go-Live Gate, nemění složení oddělení ani rozpočty `ai` a oddělení se jich účastní takto:

* **`Blok 15` (`S3` konfigurátor a tarify MRR):** `12001 marketing` nasazuje konfigurátor do kampaní a plánuje sezónní matici; `12002 obsah-geo` spravuje obchodní texty knihy tarifů. Ceny se nikdy neuvádějí mimo schválený `cenik.json`.
* **`Blok 17` (`S5` hlasová recepční):** `12002 obsah-geo` připravuje znění hlášek a odpovědí recepční ke schválení `15001`.
