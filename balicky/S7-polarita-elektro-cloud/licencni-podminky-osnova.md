# Licenční a obchodní podmínky služby Polarita Elektro Cloud — osnova · Blok 19 (S7) · Verze 3.27.1

**Stav dokumentu: `DRAFT` — koncept k revizi `15001 pravni-specialista` a advokátem.** Nejde o platný právní dokument ani o právní radu; připravila jej `ai` jako podklad. Podmínky smějí být použity vůči zákazníkovi až po revizi advokátem a schválení `1001`. Doplňuje řídicí dokument [`README.md`](README.md) (kapitola 2, pravidla 6 a 7). Všechny částky, lhůty a procenta, které zadání balíčku `S7` nestanoví, jsou vedeny jako `NÁVRH — ke schválení 1001`.

---

## 1. Osnova článků

| Čl. | Název | Obsah | Stav v této osnově |
| :--- | :--- | :--- | :--- |
| 1 | Smluvní strany a výklad pojmů | Poskytovatel (Polarita s.r.o.), Zákazník, Oprávněná osoba, Tenant, Výstup `ai`, Koncept (`DRAFT`), Vydaný dokument | osnova |
| 2 | Předmět služby | Zpřístupnění softwaru na dálku; výčet modulů podle tarifu | osnova |
| 3 | Účet, tenant a uživatelé | Správce účtu zákazníka, role, odpovědnost za přístupové údaje | osnova |
| 4 | Cena, tarify a rozpočet tokenů | Odkaz na `tarify-saas.md`; tvrdý strop tokenů; žádný příplatek za montéra | osnova (hodnoty `NÁVRH — ke schválení 1001`) |
| **5** | **Povaha služby a výstupů `ai` („Liability Firewall“)** | Software je nástroj; `ai` vytváří pouze koncepty | **plné znění níže** |
| **6** | **Rozdělení odborné odpovědnosti** | Kdo odpovídá za vydaný dokument | **plné znění níže** |
| **7** | **Povinnosti zákazníka** | Oprávnění, kontrola, vstupní data, měřidla | **plné znění níže** |
| **8** | **Odpovědnost poskytovatele a její omezení** | Za co poskytovatel odpovídá a kde odpovědnost končí | **plné znění níže** (limit `NÁVRH — ke schválení 1001`) |
| 9 | Ochrana osobních údajů | Zákazník = správce, poskytovatel = zpracovatel; zpracovatelská smlouva podle GDPR jako Příloha 1 | osnova |
| 10 | Data zákazníka, izolace, export a výmaz | Oddělení tenantů, vlastní šifrovací klíč, právo na snadnou změnu poskytovatele cloudových služeb a bezproblémový strukturovaný export dat podle platných předpisů EU o datech, lhůta výmazu po ukončení | osnova (lhůty `NÁVRH — ke schválení 1001`) |
| 11 | Dostupnost, údržba a podpora | Rozsah podpory, plánované odstávky | osnova (hodnoty `NÁVRH — ke schválení 1001`) |
| 12 | Duševní vlastnictví a licence | Nevýhradní licence k užití služby; data a dokumenty zákazníka zůstávají zákazníkovi | osnova |
| 13 | Normy, cenové soustavy, mapové podklady a zdroje třetích stran | Texty norem ČSN, databáze CS ÚRS, komerční API map a trasování (např. `Mapy.cz`) a další licencovaný obsah třetích stran nejsou zahrnuty bez příslušné licence | osnova (viz otevřené body) |
| 14 | Trvání, změna tarifu a ukončení | Výpovědní doba, pozastavení při neplacení | osnova |
| 15 | Rozhodné právo a řešení sporů | České právo; příslušnost soudu | osnova |
| 16 | Závěrečná ustanovení | Změny podmínek, oddělitelnost, pořadí dokumentů | osnova |
| Příl. 1 | Zpracovatelská smlouva | Předmět, doba, kategorie údajů, pokyny, další zpracovatelé, bezpečnost, součinnost | k vypracování |
| Příl. 2 | Popis tarifů | Převzato z `tarify-saas.md` po schválení | k vypracování |
| Příl. 3 | Technická a organizační opatření | Izolace tenantů, šifrování, zálohy, přístupy | k vypracování |
| Příl. 4 | Seznam dalších zpracovatelů a licencovaných API | Poskytovatelé hostingu, jazykových modelů a externích API (např. komerční mapové a trasovací rozhraní `Mapy.cz`, pokud se použije místo vlastního `OSM`) | k vypracování |

---

## 2. Plné znění klíčových článků (koncept)

### Článek 5 — Povaha služby a výstupů `ai` („Liability Firewall“)

5.1 Poskytovatel dodává Zákazníkovi softwarový nástroj, který obsahuje deterministické výpočetní funkce a funkce využívající umělou inteligenci (dále jen „`ai`“). Poskytovatel Zákazníkovi neposkytuje projekční, revizní, zkušební, znaleckou, rozpočtářskou, právní ani jinou odbornou službu a nevykonává za Zákazníka žádnou činnost, k níž je třeba odborná způsobilost nebo oprávnění.

5.2 Každý výstup vytvořený `ai` je pouze konceptem určeným ke kontrole odborně způsobilou osobou Zákazníka. Služba takový výstup viditelně označuje jako koncept (`DRAFT`). Koncept není revizní zprávou, protokolem, Výrobním pasem rozváděče, prohlášením o shodě, zápisem ve stavebním deníku, rozpočtem ani jiným závazným dokumentem a nesmí být jako takový předán třetí osobě.

5.3 Dokumentem se koncept stává teprve výslovným úkonem Oprávněné osoby Zákazníka, kterým tato osoba potvrdí, že obsah zkontrolovala, a dokument vlastním jménem vydá nebo podepíše (dále jen „Vydaný dokument“). Služba neumožňuje vydat dokument bez tohoto úkonu a Poskytovatel za Zákazníka žádný dokument nevydává ani nepodepisuje.

5.4 Zákazník bere na vědomí, že výstupy `ai` mohou být neúplné nebo nesprávné, i když působí věrohodně, a že přepisy hlasu, vytěžení starších dokumentů a rozpoznání hodnot z fotografií mohou obsahovat chyby. Výstup `ai` proto nenahrazuje vlastní měření, prohlídku, zkoušku ani odborný úsudek.

5.5 Deterministické výpočetní funkce provádějí výpočet nad hodnotami, které zadal Zákazník, a podle postupu popsaného v dokumentaci služby. Poskytovatel odpovídá za to, že výpočet odpovídá popsanému postupu; neodpovídá za správnost vstupních hodnot ani za rozhodnutí, zda je daný postup pro konkrétní zařízení vhodný.

### Článek 6 — Rozdělení odborné odpovědnosti

6.1 Odbornou, normovou a zákonnou odpovědnost za každý Vydaný dokument, zejména za revizní zprávu, Výrobní pas rozváděče a prohlášení o shodě, nese vždy osoba, která jej vydala nebo podepsala, a Zákazník jako zhotovitel, výrobce nebo provozovatel, a to v rozsahu vlastního oprávnění a odborné způsobilosti podle právních předpisů (v České republice zejména Oprávnění a Osvědčení podle předpisů o bezpečnosti provozu vyhrazených technických zařízení a o odborné způsobilosti v elektrotechnice).

6.2 Použití služby nezakládá spoluodpovědnost Poskytovatele za obsah Vydaného dokumentu, za jeho soulad s technickými normami a právními předpisy ani za bezpečnost zařízení, kterého se dokument týká.

6.3 Rozdělení odpovědnosti:

| Oblast | Odpovídá Poskytovatel | Odpovídá Zákazník |
| :--- | :--- | :--- |
| Dostupnost a bezpečnost služby, oddělení dat tenantů | ano | — |
| Shoda deterministického výpočtu s postupem popsaným v dokumentaci | ano | — |
| Správnost a úplnost vstupních dat, měření a fotodokumentace | — | ano |
| Platnost kalibrace měřidel a způsobilost osob | — | ano |
| Kontrola konceptu `ai` před vydáním | — | ano |
| Obsah, závěr a podpis revizní zprávy, Výrobního pasu a prohlášení o shodě | — | ano |
| Volba a správné použití technické normy v konkrétním případě | — | ano |
| Vztah ke konečným zákazníkům Zákazníka (SVJ, průmysl) | — | ano |
| Zákonnost zpracování osobních údajů vložených do služby | jako zpracovatel podle pokynů | ano, jako správce |

6.4 Zákazník odpovídá za to, že dokumenty vydává jen osoba s platným oprávněním a odbornou způsobilostí pro daný druh a rozsah zařízení. Poskytovatel platnost oprávnění Zákazníka ani jeho osob neověřuje a za ni neodpovídá, ledaže se k tomu výslovně zavázal.

6.5 Uplatní-li třetí osoba vůči Poskytovateli nárok z důvodu obsahu Vydaného dokumentu nebo činnosti Zákazníka, poskytne Zákazník Poskytovateli potřebnou součinnost a nahradí mu újmu, která mu tím vznikla, v rozsahu, v jakém ji Poskytovatel nezpůsobil porušením vlastních povinností.

### Článek 7 — Povinnosti zákazníka

7.1 Zákazník zajistí, že se službou pracují pouze osoby, které k tomu pověřil, a že činnosti vyžadující odbornou způsobilost vykonávají jen osoby, které ji mají.

7.2 Zákazník před vydáním každého dokumentu zkontroluje koncept v plném rozsahu, včetně hodnot převzatých z přepisu hlasu, z fotografií a ze starších dokumentů.

7.3 Zákazník nevkládá do služby osobní údaje, k jejichž zpracování nemá právní titul, a jako správce plní informační a další povinnosti vůči subjektům údajů.

7.4 Zákazník si sám zajišťuje přístup k licencovanému obsahu a komerčním rozhraním třetích stran, které ke své činnosti potřebuje (zejména texty technických norem, cenové soustavy a mapové podklady / API třetích stran), není-li v tarifu výslovně uvedeno jinak.

### Článek 8 — Odpovědnost poskytovatele a její omezení

8.1 Poskytovatel odpovídá za újmu způsobenou porušením svých povinností z těchto podmínek, zejména povinnosti poskytovat službu v dohodnutém rozsahu, chránit data Zákazníka a udržovat oddělení tenantů.

8.2 Poskytovatel neodpovídá za újmu vzniklou v důsledku: (a) nesprávných nebo neúplných vstupních dat, (b) vydání dokumentu bez kontroly podle čl. 7.2, (c) použití konceptu `ai` jako závazného dokumentu v rozporu s čl. 5.2, (d) vydání dokumentu osobou bez potřebného oprávnění, (e) použití služby v rozporu s dokumentací.

8.3 Celková povinnost Poskytovatele k náhradě újmy vzniklé v souvislosti se službou je omezena částkou: `NÁVRH — ke schválení 1001` (k posouzení advokátem, včetně vazby na pojistné krytí Poskytovatele).

8.4 Omezení podle čl. 8.2 a 8.3 se neuplatní na újmu způsobenou úmyslně nebo z hrubé nedbalosti, na újmu na přirozených právech člověka ani v dalších případech, kdy to právní předpisy nepřipouštějí (zejména občanské právo).

8.5 Je-li Zákazník spotřebitelem nebo slabší stranou, použijí se tato ustanovení jen v rozsahu, v jakém to právní předpisy dovolují. [K rozhodnutí: zda službu nabízet výhradně podnikatelům.]

---

## 3. Otevřené body pro `15001` a advokáta

- [ ] **Zákazníci ze Slovenské republiky:** zadání mluví o „Oprávnění TIČR“; pro SR je nutné doplnit odpovídající oprávnění a odbornou způsobilost podle slovenských předpisů a ověřit rozhodné právo a soud (čl. 6.1 a čl. 15).
- [ ] **Limit náhrady újmy (čl. 8.3)** a jeho udržitelnost vůči podnikatelům; vazba na pojištění Poskytovatele.
- [ ] **Licencovaný obsah a API třetích stran (čl. 13, 7.4 a Příloha 4):** texty norem ČSN, databáze CS ÚRS i komerční API map a trasování (`Mapy.cz` — nutno uzavřít komerční licenci a uvést poskytovatele v Příloze 4, nebo nasadit vlastní `OSRM`/`OSM`) mají vlastní licenční podmínky; je nutné ověřit rozsah oprávnění pro SaaS zákazníky.
- [ ] **Právo na změnu poskytovatele cloudových služeb a export dat (čl. 10):** nastavit smluvní a technické podmínky přenositelnosti a bezpřekážkového exportu dat zákazníka po výpovědi v souladu s platnými předpisy EU o datech (strukturovaný formát exportu, výpovědní lhůta, výmaz po předání a související poplatky/pravidla).
- [ ] **Další zpracovatelé (Příloha 4):** poskytovatelé jazykových modelů a hostingu, případné předávání údajů mimo EU a jeho právní titul.
- [ ] **Povinnosti podle předpisů EU o umělé inteligenci:** zařazení služby a z toho plynoucí informační povinnosti vůči zákazníkům.
- [ ] **Ověřování oprávnění (čl. 6.4):** zda má Poskytovatel při registraci alespoň evidovat číslo oprávnění zákazníka, a jaké důsledky by to mělo pro jeho odpovědnost.
- [ ] **Spotřebitelé (čl. 8.5):** zda službu omezit výhradně na podnikatele (B2B).
- [ ] **Doba uchování a výmaz po ukončení (čl. 10):** lhůty jsou `NÁVRH — ke schválení 1001`; zákonné archivační povinnosti k vydaným dokumentům nese zákazník.

Do vyřešení těchto bodů a do revize advokátem se podmínky nepoužívají a pilotní tenant se nezakládá.
