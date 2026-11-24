# Vzor digitálního předávacího protokolu půjčovny · Blok 16 · Verze 3.2.3

Vzor pro modul `pujcovna-meridel`. Protokol vzniká v PWA `portal-spolupracovniku`, sází se v `Typst` do PDF, opatří se serverovou pečetí `pyHanko` s časovým razítkem a uloží se ke spisu výpůjčky. Proměnné ve složených závorkách doplní systém; hodnoty bez schválení `1001` (ceník, výše kauce, minimální počet fotografií) jsou `NÁVRH — ke schválení 1001` a tento vzor žádné částky neobsahuje.

Jména a kontakty podepisujících se doplní až do vysázeného PDF z registru kontaktů; ve schématu `pujcovna` se ukládá jen odkaz. Vysázený protokol se nikdy neukládá do Vaultu.

Vzor popisuje **dva samostatné záznamy** entity `handover_protocol`: Část A (směr `HANDOVER`) se podepisuje a pečetí při předání, Část B (směr `RETURN`) při vrácení. Každý záznam má vlastní PDF, vlastní podpisy a vlastní pečeť; PDF vrácení obsahuje úvodní tabulky a Část A jen jako nezměněný opis pro porovnání. Oddíl „Vypořádání kauce“ není součástí žádného z pečetěných protokolů — je to samostatný podklad z deníku kaucí a rozhodnutí `1001` v `Decisions`.

---

## Protokol o předání a vrácení č. `{{protocol_no}}`

| Údaj | Hodnota |
| :--- | :--- |
| Spis výpůjčky | `{{case_id}}` (`POL-RRRR-NNNNN`) |
| Rezervace | `{{reservation_id}}`, období `{{period_from}}` – `{{period_to}}` |
| Pronajímatel | Polarita s.r.o., IČO 14180324, DIČ CZ14180324, Na Folimance 2155/15, 120 00 Praha 2 |
| Nájemce | `{{renter_name}}`, IČO `{{renter_ico}}`, typ `{{renter_type}}` (`Certified Partner SUB` / B2B zákazník) |
| Smluvní podklad | `{{framework_contract_ref}}` (podmínky půjčovny schválené `1001`) |

### 1. Předmět výpůjčky

| Údaj | Hodnota |
| :--- | :--- |
| Zdroj | `{{asset_name}}` |
| Kategorie | `{{asset_category}}` (analyzátor sítí / termokamera / tester EV nabíječek / mobilní staveništní rozváděč / elektrocentrála) |
| Výrobní číslo | `{{serial_number}}` |
| QR zdroje | `{{asset_qr}}` |
| Domovský sklad | `{{home_warehouse}}` |

### 2. Kalibrace nebo revize (otisk z Lhůtníku v okamžiku předání)

| Údaj | Hodnota |
| :--- | :--- |
| Druh | `{{compliance_kind}}` (kalibrace měřidla / revize či kontrola zdroje nebo rozváděče) |
| Doklad | `{{compliance_document_ref}}` |
| Platnost do | `{{compliance_valid_until}}` |
| Kontrola | ☐ platí po celou dobu výpůjčky (bez toho systém předání nepovolí) |

### 3. Kauce

| Údaj | Hodnota |
| :--- | :--- |
| Výše kauce | `{{kauce}}` `{{kauce_mena}}` |
| Stav kauce při předání | `{{deposit_status}}` (přijata na účet / nevybírá se podle rozhodnutí `1001` č. `{{deposit_waiver_decisions_ref}}`) |
| Spárování s výpisem | `{{bank_match_ref}}` |

---

## Část A — Předání nájemci

| Údaj | Hodnota |
| :--- | :--- |
| Datum a čas předání | `{{handover_at}}` |
| Místo | `{{handover_place}}` |
| Za Polaritu předal | osobní číslo `{{polarita_person_no}}` |
| Za nájemce převzal | `{{renter_signer_name}}` |
| Stav při předání | ☐ bez závad ☐ běžné opotřebení ☐ poškozeno ☐ neúplné ☐ nefunkční |
| Popis stavu | `{{handover_condition_note}}` |
| Motohodiny / stav paliva (jen elektrocentrála) | `{{handover_operating_hours}}` / `{{handover_fuel_level_percent}}` % |

**Příslušenství při předání:**

| Položka | Předáno |
| :--- | :--- |
| `{{accessory_1}}` | ☐ ano ☐ ne |
| `{{accessory_2}}` | ☐ ano ☐ ne |
| `{{accessory_n}}` | ☐ ano ☐ ne |

**Fotodokumentace při předání** (minimální počet `{{min_fotek}}` — `NÁVRH — ke schválení 1001`):

| Č. | Co je na fotografii | Soubor v `Garage` | Čas pořízení |
| :--- | :--- | :--- | :--- |
| 1 | Celkový pohled | `{{handover_photo_1}}` | `{{handover_photo_1_at}}` |
| 2 | Výrobní štítek a QR | `{{handover_photo_2}}` | `{{handover_photo_2_at}}` |
| 3 | Displej / ovládací panel / stav počitadla | `{{handover_photo_3}}` | `{{handover_photo_3_at}}` |
| 4 | Příslušenství | `{{handover_photo_4}}` | `{{handover_photo_4_at}}` |
| n | Existující vady a oděrky | `{{handover_photo_n}}` | `{{handover_photo_n_at}}` |

**Potvrzení nájemce při předání:**

- ☐ Převzal jsem zdroj a příslušenství ve stavu popsaném výše.
- ☐ Byl jsem seznámen s návodem k obsluze a s bezpečnostními pokyny.
- ☐ Beru na vědomí, že zdroj smí obsluhovat jen osoba s odpovídající kvalifikací.

Podpis za Polaritu: `{{polarita_signature_handover}}` · Podpis za nájemce: `{{renter_signature_handover}}`

---

## Část B — Vrácení Polaritě

| Údaj | Hodnota |
| :--- | :--- |
| Datum a čas vrácení | `{{return_at}}` |
| Místo | `{{return_place}}` |
| Za nájemce vrátil | `{{renter_return_signer_name}}` |
| Za Polaritu převzal | osobní číslo `{{polarita_return_person_no}}` |
| Stav při vrácení | ☐ bez závad ☐ běžné opotřebení ☐ poškozeno ☐ neúplné ☐ nefunkční |
| Popis stavu a rozdílů proti předání | `{{return_condition_note}}` |
| Motohodiny / stav paliva (jen elektrocentrála) | `{{return_operating_hours}}` / `{{return_fuel_level_percent}}` % |
| Kalibrace nebo revize při vrácení | platí do `{{return_compliance_valid_until}}`; ☐ zdroj lze vrátit do skladu ☐ zdroj jde do servisu / na kalibraci |

**Příslušenství při vrácení:**

| Položka | Vráceno |
| :--- | :--- |
| `{{accessory_1}}` | ☐ ano ☐ ne |
| `{{accessory_2}}` | ☐ ano ☐ ne |
| `{{accessory_n}}` | ☐ ano ☐ ne |

**Fotodokumentace při vrácení** (stejné záběry jako při předání, aby šly porovnat):

| Č. | Co je na fotografii | Soubor v `Garage` | Čas pořízení |
| :--- | :--- | :--- | :--- |
| 1 | Celkový pohled | `{{return_photo_1}}` | `{{return_photo_1_at}}` |
| 2 | Výrobní štítek a QR | `{{return_photo_2}}` | `{{return_photo_2_at}}` |
| 3 | Displej / ovládací panel / stav počitadla | `{{return_photo_3}}` | `{{return_photo_3_at}}` |
| 4 | Příslušenství | `{{return_photo_4}}` | `{{return_photo_4_at}}` |
| n | Nové vady a poškození | `{{return_photo_n}}` | `{{return_photo_n_at}}` |

**Škody a chybějící položky:** `{{damage_description}}` (každá škoda se zakládá jako samostatný záznam a schvaluje ji `1001` v `Decisions`).

Podpis za nájemce: `{{renter_signature_return}}` · Podpis za Polaritu: `{{polarita_signature_return}}`

---

## Vypořádání kauce (samostatný podklad, vyplňuje se po vrácení)

Pokud se kauce nevybírala (stav `WAIVED`), oddíl se nevyplňuje a případná škoda se řeší jen záznamem škody a fakturou.

| Údaj | Hodnota |
| :--- | :--- |
| Složená kauce | `{{kauce}}` `{{kauce_mena}}` |
| Zadržená část a důvod | `{{kauce_zadrzeno}}` `{{kauce_mena}}` — `{{kauce_duvod_zadrzeni}}` |
| Vrácená část | `{{kauce_vraceno}}` `{{kauce_mena}}` |
| Rozhodnutí `1001` v `Decisions` | `{{deposit_settlement_decisions_ref}}` |

Návrh vypořádání připraví `16001 ucetni` jako `DRAFT`. Vrácení i zadržení kauce potvrzuje `1001`; `ai` žádnou platbu neodesílá.

---

## Technická patička (v PDF před pečetěním)

| Údaj | Hodnota |
| :--- | :--- |
| Protokol a spis | `{{protocol_no}}` / `{{case_id}}` |
| Šablona a datum sazby | `{{template_version}}` (`Typst`), vygenerováno `{{rendered_at}}` |
| Cílové uložení | `Garage`, objekt `{{pdf_key}}`; archivace ke spisu dle spisového plánu |

> **Externí metadata po zapečetění (ukládají se vedle PDF v DB a spisu, nikdy uvnitř samotného těla PDF před výpočtem otisku):** `pdf_sha256` (kontrolní otisk výsledného zapečetěného souboru) a `seal_ref` (`pyHanko` + TSA časové razítko).

## Pravidla, která systém u protokolu vynucuje

1. Bez přijaté kauce (nebo bez zapsaného rozhodnutí `1001` v `Decisions`, že se kauce nevybírá) a bez zapečetěné Části A zdroj nesmí opustit sklad.
2. Kalibrace nebo revize musí podle Lhůtníku platit až do plánovaného vrácení; jinak předání nelze dokončit.
3. Protokol nelze podepsat, dokud není odškrtnuto všechno příslušenství a nahrán minimální počet fotografií.
4. Po zapečetění se protokol nemění; oprava je nový protokol s odkazem `supersedes_protocol_id` na původní. Náhrada musí patřit ke stejné výpůjčce a mít stejný směr (Část A nahrazuje jen Část A, Část B jen Část B téže výpůjčky); databáze to vynucuje a jiný protokol jako náhradu nepřijme. Náhradní protokol se podepíše a zapečetí, dokud původní ještě platí, a teprve ve stejné transakci se zapečetěním náhrady přechází původní s potvrzením `1001` do stavu `SUPERSEDED` (zůstává archivován). Nezapečetěný protokol, který se nepoužije, se s důvodem označí jako `DISCARDED`.
5. Po zapečetěné Části B jde zdroj do stavu kontroly po vrácení a zpět do nabídky se dostane až po přijetí skladem nebo po servisu. Stav výpůjčky a stav zdroje se při předání i vrácení mění společně jednou operací, nikdy jeden bez druhého.
6. Nevrátí-li se zdroj do plánovaného termínu, přejde výpůjčka do stavu `OVERDUE`: zdroj od té chvíle blokuje nové žádosti i potvrzení a jeho návazné rezervace jdou do `Decisions`; vrácení v prodlení je řádná Část B. Pokud se zdroj nevrátí vůbec, Část B nevzniká: výpůjčka přejde s potvrzením `1001` do stavu `NOT_RETURNED`, ztráta se založí jako škoda bez vratného protokolu a vyúčtování proběhne bez Části B. Zdroj se odepisuje až při uzavření případu ztráty, ve stejné operaci jako uzavření výpůjčky.
7. Vrátí-li se zdroj po ohlášené ztrátě dřív, než je případ uzavřen, vzniká řádná Část B: pozdní vrácení potvrzuje `1001` v `Decisions`, zapisuje se do auditní stopy, zdroj jde do kontroly po vrácení jako při každém jiném vrácení a škoda se ztrátou se přehodnotí (pokračuje jako běžná škoda, nebo ji `1001` zamítne). Zdroj nalezený až po odpisu se tímto postupem nevrací; o jeho novém zařazení rozhodne `1001`.

## Poznámka k návrhu

Vzor je návrh. Smluvní podmínky půjčovny (odpovědnost za škodu, pojištění, sankce za pozdní vrácení, rozsah poučení) připraví `15001 pravni-specialista` a schvaluje je `1001`; do té doby nejde o závazný smluvní dokument.
