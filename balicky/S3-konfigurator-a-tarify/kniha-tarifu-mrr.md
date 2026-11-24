# GTM kniha tarifů MRR — paušál „Elektro Správa SVJ a Firem“ · Verze 3.19

Obchodní kniha pro `12001 marketing`, `12002 obsah-geo`, `14005 zakazky` a živé obchodníky. Popisuje, **co který tarif obsahuje a jak se prodává**. Částky zde záměrně nejsou — jediným zdrojem cen je [`cenik.json`](./cenik.json) a z něj generovaný [`prehled-cen.md`](./prehled-cen.md) (stav `SCHVÁLENO 1001`, 15. 11. 2026).

## 1. Zásady tarifů

1. **Platí se za objekt, ne za lidi.** Cena se odvíjí od počtu objektů a dalších vchodů. Počet členů výboru SVJ ani uživatelů portálu cenu nemění.
2. **Vyšší tarif vždy obsahuje vše z nižšího.** Zákazník může tarif kdykoli zvýšit; snížení je možné k výročí smlouvy.
3. **Indexace.** Paušál se jednou ročně upravuje o míru inflace vyhlášenou ČSÚ podle paušální servisní smlouvy (sestava č. 2 balíčku `S1`).
4. **Žádné sliby mimo smlouvu.** Garantované lhůty SLA platí jen v rozsahu uvedeném u tarifu a ve smlouvě. `ai` nikdy neslibuje cenu ani termín nad rámec ceníku a smlouvy.

## 2. Tři tarify

| | **Start SVJ** | **Standard Objekt** | **Maxi Areál / B2B** |
| :--- | :--- | :--- | :--- |
| **Pro koho** | SVJ a bytová družstva | SVJ, bytové domy a menší firmy | Areály, výrobní a logistické firmy |
| **48h digitální převzetí starých šanonů (`N7`)** | ano | ano | ano |
| **Hlídání všech lhůt v Centrálním Lhůtníku** | ano | ano | ano |
| **Digitální kniha objektu pod QR kódem na rozváděči** | ano | ano | ano |
| **Pravidelné revize společných prostor a hromosvodu LPS v ceně** | ano | ano | ano |
| **Neomezený počet členů výboru / uživatelů v portálu** | ano | ano | ano |
| **Termovizní diagnostika hlavních rozváděčů** | — | ano | ano |
| **Prioritní servisní SLA odezva přes Helpdesk** | — | ano | ano |
| **Vzdálený `Read-Only` dohled EV wallboxů (`OCPP`) a FVE střídačů** | — | ano | ano |
| **Roční souhrnná zpráva pro pojišťovnu** | — | ano | ano |
| **Garantovaná pohotovostní SLA lhůta** | — | — | ano |
| **Preventivní údržba trafostanic, kompenzací a nouzového osvětlení** | — | — | ano |
| **Zvýhodněná hodinová sazba montérů** | — | sleva 5 % | sleva 10 % |
| **Prioritní dispečink a koordinace zakázek (`14005 zakazky`)** | — | — | ano |

## 3. Produktizované balíčky na klíč (cena od–do)

1. **Chytrý EV Wallbox pro garáž SVJ / rodinný dům** — včetně dynamického řízení výkonu DLM a `OCPP` dohledu.
2. **Modernizace stoupaček a hlavního elektroměrového rozváděče SVJ** — s Výrobním pasem CE podle platné normy pro rozváděče nízkého napětí.
3. **Komunitní a firemní FVE + BESS** — s datovou připraveností pasu baterie (předpisy EU o bateriích, povinné od 18. 2. 2027 pro LMT, EV a průmyslové baterie > 2 kWh), registrací EDC a požární revizí.

Rozsah „od–do“ se zákazníkovi vždy vysvětluje: dolní mez = nejjednodušší provedení, horní mez = složité trasy, vyšší výkon nebo stavební přípomoce. Přesnou cenu určí rozpočet `14002 rozpoctar` po prohlídce.

## 4. Prodejní postup

1. **Vstup:** Kalkulačka rizik a úspor SVJ (`/kalkulacka-svj`, `N6`) → konfigurátor → poptávka do 360° Karty spisu.
2. **Kvalifikace (`14005 zakazky`):** počet objektů a vchodů, stav dokumentace (šanony), termíny propadlých revizí.
3. **Nabídka (`14002 rozpoctar`):** tarif z konfigurace + případné balíčky na klíč; kontrola minimální marže; schválení `1001` v `Decisions`.
4. **Smlouva:** paušální servisní smlouva MRR ze šablony `S1` (kontrola `15001`), podpis `1001`; s balíčkem `S5` dvoustranně elektronicky.
5. **Start služby:** 48h převzetí šanonů, založení lhůt v Lhůtníku, QR štítky Digitální knihy objektu, aktivace fakturačního kalendáře.
6. **Partner:** přivedl-li objekt `Certified Partner SUB`, vzniká mu trvalá provize z uhrazeného MRR podle [`kalkulacni-matice.md`](./kalkulacni-matice.md).

## 5. Co se v komunikaci nesmí

- Uvádět ceny, které nejsou ve schváleném ceníku, nebo je prezentovat jako závazné před schválením v `Decisions`.
- Slibovat výsledek revize, úsporu nebo výši pojistného plnění.
- Zveřejnit jmennou referenci bez souhlasu klienta a `1001`.
