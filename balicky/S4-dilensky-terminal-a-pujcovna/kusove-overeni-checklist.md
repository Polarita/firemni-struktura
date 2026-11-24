# Checklist kusového ověření rozváděče · platná norma pro rozváděče nízkého napětí · Blok 16 · Verze 3.8

Tento checklist je podklad pro povinný formulář kiosku `dilensky-terminal`. Je to **návrh k odbornému ověření**: záměrně neuvádí čísla článků normy ani mezní hodnoty. Ty se při každém ověření načítají z normové báze ve Vaultu (`03-Normy-a-Metodiky/`), kterou vede `15002 normovac`, a verze normové báze se uloží k záznamu. Kde je v tabulce napsáno „dle registru `15002`“, znamená to „dle platného znění normy v normové bázi ve Vaultu (`03-Normy-a-Metodiky/`), kterou spravuje `15002`“.

Kusové ověření se provádí na **každém** vyrobeném rozváděči a hledá vady materiálu a provedení. Neopakuje ověření návrhu.

## Hlavička záznamu

| Údaj | Hodnota |
| :--- | :--- |
| Spis | `{{case_id}}` (`POL-RRRR-NNNNN`) |
| Rozváděč — typové označení | `{{type_designation}}` |
| Výrobní číslo | `{{serial_number}}` (přiděluje `cz-sk-registry-kernel`) |
| Výrobková část normy | `{{product_standard_ref}}` (příslušná výrobková norma — dle registru `15002`) |
| Verze registru norem | `{{standards_register_ref}}` |
| Ověření provedl | osobní číslo `{{verifier_person_no}}` |
| Datum a místo | `{{opened_at}}`, `{{warehouse_code}}` (z karty rozváděče), kiosk `{{station_code}}` |

## A. Předpoklady (`Hard-Stop` — bez nich nelze ověření otevřít ani uzavřít)

Tyto řádky **nejsou body kusového ověření**. Jsou to zámky, které kiosk vyhodnocuje na serveru.

| Č. | Předpoklad | Způsob | Kritérium | Výsledek |
| :--- | :--- | :--- | :--- | :--- |
| A1 | Ověření návrhu rozváděče včetně oteplení | Kontrola odkazu na dokument z `cad-urs-engine` | Ověření návrhu existuje a oteplení je ověřeno **výpočtem** podle platné metodiky; oteplení se při kusovém ověření neměří | ☐ splněno ☐ nesplněno |
| A2 | Úplnost kusovníku | Porovnání skenů `S/N` s kusovníkem | Každý řádek kusovníku s povinným `S/N` má naskenovaný přístroj | ☐ splněno ☐ nesplněno |
| A3 | Způsobilost osoby | Dotaz na `portal-spolupracovniku` (Clean Room) | Stav `ZPŮSOBILÝ: ANO`; požadovaný stupeň kvalifikace podle předpisů o odborné způsobilosti v elektrotechnice je `NÁVRH — ke schválení 1001` | ☐ splněno ☐ nesplněno |
| A4 | Kalibrace použitých měřidel | Dotaz na Lhůtník po naskenování `QR měřidla` | Každé použité měřidlo má v den zkoušky platnou kalibraci | ☐ splněno ☐ nesplněno |

## B. Kusové ověření — provedení (konstrukce)

| Č. | Bod ověření | Způsob | Kritérium | Výsledek |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Stupeň ochrany krytem | Vizuální kontrola krytu, těsnění, průchodek a záslepek | Provedení odpovídá stupni ochrany uvedenému v dokumentaci rozváděče; požadavky dle registru `15002` | ☐ VYHOVUJE ☐ NEVYHOVUJE ☐ NEPOUŽIJE SE |
| 2 | Vzdušné vzdálenosti a povrchové cesty | Vizuální kontrola; při pochybnosti měření nebo zkouška dle registru `15002` | Vzdálenosti odpovídají ověřenému návrhu; mezní hodnoty dle registru `15002` | ☐ VYHOVUJE ☐ NEVYHOVUJE ☐ NEPOUŽIJE SE |
| 3 | Ochrana před úrazem elektrickým proudem a integrita ochranných obvodů (PE) | Vizuální kontrola ochranných opatření a spojů ochranného obvodu; kontrola dotažení spojů; měření spojitosti ochranného obvodu kalibrovaným měřidlem | Ochranná opatření jsou provedena dle dokumentace; ochranný obvod je spojitý; rozsah zkoušky a mezní hodnoty dle registru `15002` | ☐ VYHOVUJE ☐ NEVYHOVUJE ☐ NEPOUŽIJE SE |
| 4 | Vestavění vestavných součástí | Vizuální kontrola proti kusovníku a pokynům výrobců přístrojů | Typy, osazení a označení přístrojů odpovídají kusovníku a schématu z `cad-urs-engine` | ☐ VYHOVUJE ☐ NEVYHOVUJE ☐ NEPOUŽIJE SE |
| 5 | Vnitřní elektrické obvody a spoje | Vizuální kontrola; kontrola dotažení šroubových spojů v rozsahu dle registru `15002` | Spoje jsou provedeny a dotaženy dle dokumentace; utahovací momenty dle pokynů výrobců přístrojů | ☐ VYHOVUJE ☐ NEVYHOVUJE ☐ NEPOUŽIJE SE |
| 6 | Svorky pro vnější vodiče | Vizuální kontrola počtu, typu a označení svorek | Svorky odpovídají dokumentaci a jsou jednoznačně označeny | ☐ VYHOVUJE ☐ NEVYHOVUJE ☐ NEPOUŽIJE SE |
| 7 | Mechanická funkce | Ruční vyzkoušení ovládacích prvků, blokování, zámků a výsuvných částí | Prvky fungují bez závad dle dokumentace | ☐ VYHOVUJE ☐ NEVYHOVUJE ☐ NEPOUŽIJE SE |

## C. Kusové ověření — funkce

| Č. | Bod ověření | Způsob | Kritérium | Výsledek |
| :--- | :--- | :--- | :--- | :--- |
| 8 | Dielektrické vlastnosti | Zkouška výdržným napětím; tam, kde to norma připouští, měření izolačního odporu — volbu postupu určuje registr `15002`; vždy kalibrovaným měřidlem | Zkušební napětí, doba zkoušky a mezní hodnota izolačního odporu dle registru `15002`; naměřená hodnota se zapisuje | ☐ VYHOVUJE ☐ NEVYHOVUJE ☐ NEPOUŽIJE SE |
| 9 | Zapojení, pracovní charakteristiky a funkce | Kontrola zapojení proti schématu; kontrola úplnosti označení a dokumentace; funkční zkouška v rozsahu dle registru `15002` | Zapojení odpovídá schématu, označení a dokumentace jsou úplné, rozváděč plní předepsanou funkci | ☐ VYHOVUJE ☐ NEVYHOVUJE ☐ NEPOUŽIJE SE |

U bodů 3 a 8 kiosk vyžaduje naskenování `QR měřidla`, zápis naměřené hodnoty s jednotkou a platnou kalibraci v den zkoušky; způsob bez měřidla u nich zvolit nelze. Stejné požadavky platí u kteréhokoli jiného bodu, pokud se u něj měří nebo zkouší přístrojem (například bod 2 při pochybnosti). Výrok `NEPOUŽIJE SE` kiosk nabídne jen u bodu, který registr `15002` pro daný typ výrobku označí jako nepoužitelný, a vždy vyžaduje písemné zdůvodnění; všech devět bodů takto uzavřít nelze. Výrok `NEVYHOVUJE` vyžaduje popis závady a doporučeně fotografii.

## D. Závěr

| Údaj | Hodnota |
| :--- | :--- |
| Použitá měřidla | `{{instruments}}` (QR, kalibrace platná do, číslo kalibračního listu) |
| Celkový výrok | ☐ `VYHOVUJE` (všechny body 1–9 mají `VYHOVUJE` nebo zdůvodněné `NEPOUŽIJE SE`) ☐ `NEVYHOVUJE` (aspoň jeden bod `NEVYHOVUJE`) |
| Zjištěné závady | `{{defects}}` |
| Ověření uzavřel | osobní číslo `{{verifier_person_no}}`, `{{closed_at}}` |

## Co následuje po uzavření

1. Při `VYHOVUJE` vloží `cad-urs-engine` protokol do Výrobního pasu a připraví `DRAFT` EU prohlášení o shodě.
2. Po kontrole `15002 normovac` prohlášení v `Decisions` potvrdí a osobním kvalifikovaným podpisem podepíše `1001`. `ai` podpis nevytváří.
3. Teprve potom kiosk odemkne tisk štítku CE s QR a podkladu `PHE` a `elektro-wms` uvolní expedici. Podklady se ověřují znovu při každém tisku i schváleném přetisku.
4. Při `NEVYHOVUJE` se štítek netiskne a rozváděč se vrací do kompletace. Po opravě se zakládá nové ověření; původní záznam zůstává beze změny. Bylo-li chybné samo ověření a `1001` je zneplatnil, opakuje se zkouška s jeho potvrzením na novém záznamu bez opravy.
5. Nedokončené ověření lze opustit jen se zapsaným důvodem; rozváděč se vrací do stavu po kompletaci a nové ověření je nový záznam.
6. Uzavřené ověření může zneplatnit jen `1001` v `Decisions` s důvodem. Dosud nevytištěné uvolněné tiskové úlohy se zamknou ve stejné operaci. Prohlášení o shodě se pak odvolá, pas a vytištěné štítky se zneplatní a rozváděč se vrací do ověření, i když už byl označen nebo uvolněn k expedici.

## Poznámky k návrhu

- Zadání balíčku `S4` jmenuje jako body kusové zkoušky oteplení, izolační odpor a spojitost ochranného obvodu PE. Izolační odpor je zde součástí bodu 8, spojitost PE součástí bodu 3. Oteplení je přesunuto do předpokladu A1, protože jde o ověření návrhu výpočtem, ne o kusovou zkoušku.
- Měření spojitosti ochranného obvodu v bodu 3 je do checklistu zařazeno podle zadání `S4`; zda jde o požadavek normy, nebo o interní požadavek Polarity nad její rámec, potvrdí `15002 normovac`.
- Checklist před nasazením projde kontrolou `15002 normovac` a schválením `1001`; do té doby je to návrh, ne závazný zkušební předpis.
