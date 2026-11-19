# Přehled cen a sazeb (generováno z `cenik.json`)

> **Stav: `SCHVALENO_1001`** — Výchozí ceník schválil jednatel 1001 dne 15. 11. 2026 ve znění návrhu, beze změn. Hodnoty nebyly porovnány s trhem ani s nákupními ceníky; při založení firmy se schválení zapíše do Decisions jako výchozí stav a každá další změna prochází mutation_confirm. Nejde o závaznou nabídku zákazníkovi.
> Tento soubor se neupravuje ručně; vzniká příkazem `python pricing.py --build`.

## Tarify paušálu „Elektro Správa SVJ a Firem“ (MRR, bez DPH)

| Tarif | Měsíčně za objekt | Další vchod / měsíc | SLA odezva | Sleva na práci |
| :--- | ---: | ---: | :--- | ---: |
| **Start SVJ** | 1 490 Kč | 490 Kč | následující pracovní den | 0 % |
| **Standard Objekt** | 2 990 Kč | 790 Kč | do 8 pracovních hodin | 5 % |
| **Maxi Areál / B2B** | 6 900 Kč | 1 490 Kč | garantovaná pohotovost do 4 hodin | 10 % |

## Balíčky na klíč (cena od–do, bez DPH)

| Balíček | Jednotka | Od | Do |
| :--- | :--- | ---: | ---: |
| Chytrý EV Wallbox pro garáž SVJ / rodinný dům | ks | 38 000 Kč | 95 000 Kč |
| Modernizace stoupaček a hlavního elektroměrového rozváděče SVJ | vchod | 180 000 Kč | 950 000 Kč |
| Komunitní a firemní FVE + BESS | instalace | 450 000 Kč | 3 500 000 Kč |

## Hodinové zúčtovací sazby (HZS, bez DPH)

| Role | Kč / h |
| :--- | ---: |
| Montér-elektrotechnik | 590 Kč |
| Vedoucí elektrotechnik | 690 Kč |
| Revizní technik (TIČR) | 990 Kč |
| Projektant elektro | 1 190 Kč |

## Přirážky, minimální marže a provize

- Přirážka na materiál z `Elektro WMS`: **15 %**
- Minimální krycí příspěvek zakázky (`Hard-Stop` bez podpisu `1001`): **22 %**
- Zádržné: **5–10 %** (dáno návrhem firmy)

| Přivedených aktivních objektů | Trvalá provize z uhrazeného MRR |
| ---: | ---: |
| od 1 | 10,0 % |
| od 5 | 12,5 % |
| od 10 | 15,0 % |

## Sezónní koeficienty balíčků na klíč

| Měsíce | Koeficient | Období |
| :--- | ---: | :--- |
| 1, 2 | 0,95 | Zimní útlum montáží |
| 3, 4, 5 | 1,0 | Jarní standard |
| 6, 7, 8, 9 | 1,05 | Hlavní sezóna FVE a EV |
| 10, 11, 12 | 1,0 | Podzimní revize |

**Indexace:** Roční indexace paušálu o průměrnou míru inflace vyhlášenou ČSÚ za předchozí kalendářní rok (dle paušální servisní smlouvy, sestava S1 č. 2).
