# Tarify SaaS edice Polarita Elektro Cloud — struktura · Blok 19 (S7) · Verze 3.20.1

Tento dokument popisuje **strukturu** tří tarifů (`Solo RT` / `Elektro Tým` / `Elektro Firma`). Doplňuje řídicí dokument [`README.md`](README.md) (kapitola 2, pravidlo 5). **Neobsahuje žádnou cenu ani číselný limit** — zadání balíčku `S7` je nestanoví, proto jsou všechny vedeny jako `NÁVRH — ke schválení 1001` a doplní je `1001` až po splnění brány `Go / No-Go`. Tarify nejsou zveřejněny ani nabízeny; Polarita Elektro Cloud ve Verzi 3.20.1 není spuštěn.

---

## 1. Zásady společné všem tarifům

1. **Předplatné za celou firmu, ne za hlavu (fair-use):** cena tarifu se nikdy nenásobí počtem montérů v terénu (přibrání terénního montéra nesmí zákazníka stát příplatek v mezích běžného provozu — *fair-use* strop pro každý tarif a jasné oddělení od plných kancelářských/revizních účtů schvaluje `1001` před spuštěním).
2. **Měřený rozpočet tokenů s tvrdým stropem na tenant:** každý tarif obsahuje měsíční rozpočet tokenů pro `ai` funkce. Spotřeba se měří na tenant a zákazník ji vidí průběžně. Po dosažení stropu se zastaví **pouze `ai` funkce** daného tenanta; deterministické funkce (výpočty `cad-urs-engine`, Lhůtník, Digitální kniha objektu, stavební deník, registry) běží dál.
3. **Žádné automatické přečerpání:** strop se sám nenavyšuje a nad strop se nic neúčtuje bez výslovné objednávky zákazníka. Způsob dokoupení rozpočtu je `NÁVRH — ke schválení 1001`.
4. **Oddělení od interního provozu:** spotřeba tenantů se nikdy neúčtuje do interního stropu `470 USD / měsíc` společnosti Polarita s.r.o. a naopak.
5. **Stejná izolace a stejný `Liability Firewall` ve všech tarifech:** sdílené schéma se složeným klíčem, `FORCE` a `AS RESTRICTIVE` `Row-Level Security` (`TO PUBLIC`, kontext tenanta jen tokenem relace), vlastní klíč v `OpenBao`, vlastní `Clean Room` (`security_invoker = true`) a pravidlo „`ai` generuje jen `DRAFT`“ nejsou příplatkovou funkcí — platí od nejnižšího tarifu.
6. **Odborná odpovědnost se tarifem nemění:** v žádném tarifu nepřebírá Polarita s.r.o. odpovědnost za vydanou revizní zprávu, Výrobní pas ani prohlášení o shodě (viz `licencni-podminky-osnova.md`).

---

## 2. Tři tarify — komu jsou určeny

| Tarif | Pro koho | Charakter |
| :--- | :--- | :--- |
| **`Solo RT`** | Samostatný revizní technik nebo jednočlenná elektro živnost | Jeden odborný uživatel, důraz na revize, Lhůtník a Digitální knihu objektu |
| **`Elektro Tým`** | Menší elektro firma s montážní četou a kanceláří | Více rolí (revize, rozpočty, montáž, kancelář), stavební deník, plánování zdrojů |
| **`Elektro Firma`** | Větší elektro firma s více četami, výrobou rozváděčů a vlastními SVJ / průmyslovými zákazníky | Plný rozsah včetně Výrobních pasů rozváděčů, klientského portálu pod vlastním logem a hlasové kanceláře |

Rozřazení funkcí do tarifů v kapitole 3 je návrh struktury; které funkce budou v kterém tarifu skutečně obsaženy, je `NÁVRH — ke schválení 1001`.

---

## 3. Obsah tarifů (struktura k rozhodnutí)

Produktový rozsah vychází ze čtyř bodů zadání `S7`. Buňka `NÁVRH` znamená `NÁVRH — ke schválení 1001` (zařadit / nezařadit / zařadit s omezením).

| Funkce | `Solo RT` | `Elektro Tým` | `Elektro Firma` |
| :--- | :--- | :--- | :--- |
| Digitální kniha objektu s QR štítky | `NÁVRH` | `NÁVRH` | `NÁVRH` |
| Centrální Lhůtník | `NÁVRH` | `NÁVRH` | `NÁVRH` |
| 48h `ai` vytěžení starých šanonů | `NÁVRH` | `NÁVRH` | `NÁVRH` |
| Klientský portál pod logem zákazníka (pro jeho SVJ a průmyslové odběratele) | `NÁVRH` | `NÁVRH` | `NÁVRH` |
| `ai` asistent revizního technika (koncept revizní zprávy, `DRAFT`) | `NÁVRH` | `NÁVRH` | `NÁVRH` |
| `ai` asistent rozpočtáře CS ÚRS (kontrola 9 vrstev přípomocí) | `NÁVRH` | `NÁVRH` | `NÁVRH` |
| Hlasová kancelář (`WhisperX` — přepis dohod o vícepracích, diktování) | `NÁVRH` | `NÁVRH` | `NÁVRH` |
| Generátor Výrobního pasu rozváděče podle platné normy pro rozváděče nízkého napětí (výpočet oteplení podle platné metodiky + `CE`) | `NÁVRH` | `NÁVRH` | `NÁVRH` |
| Elektronický stavební deník s hlasovým diktováním | `NÁVRH` | `NÁVRH` | `NÁVRH` |
| Bezkolizní kalendář zdrojů a trasy (komerční licence `Mapy.cz` API nebo vlastní routing nad `OSM`) | `NÁVRH` | `NÁVRH` | `NÁVRH` |
| Česko-slovenské jádro `cz-sk-registry-kernel` (`ARES`, `ADIS`, `ISIR`, `CEE`, `RPO`, `RegisterUZ`, `ISDOC` / `Peppol`, připravenost na případnou zákonnou evidenci tržeb) | `NÁVRH` | `NÁVRH` | `NÁVRH` |

---

## 4. Ceny a limity

Žádná hodnota v této tabulce není stanovena. Každá buňka = `NÁVRH — ke schválení 1001`.

| Parametr | `Solo RT` | `Elektro Tým` | `Elektro Firma` |
| :--- | :--- | :--- | :--- |
| Měsíční cena bez DPH | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` |
| Cena při roční platbě | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` |
| Počet spravovaných objektů | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` |
| Úložiště dokumentů a fotodokumentace | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` |
| Měsíční rozpočet tokenů (tvrdý strop) | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` |
| Hranice varování před stropem tokenů | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` |
| Objem přepisu hlasu (`WhisperX`) | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` |
| Počet kancelářských účtů a *fair-use* strop terénních montérů (bez příplatku za hlavu) | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` |
| Úroveň podpory a doba odezvy | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` | `NÁVRH — ke schválení 1001` |

---

## 5. Co musí `1001` rozhodnout před zveřejněním

- [ ] Ceny všech tří tarifů, fakturační období, měna pro ČR a SR a režim DPH (podklad: výpočet nákladů od `11001 ceo` a `16001 ucetni`).
- [ ] Číselné limity z kapitoly 4 a chování při dosažení limitu objektů a úložiště (limit tokenů je vždy tvrdý strop — to se nemění).
- [ ] Rozřazení funkcí do tarifů z kapitoly 3.
- [ ] Způsob dokoupení rozpočtu tokenů a to, zda nevyčerpaný rozpočet přechází do dalšího měsíce.
- [ ] Zkušební období, podmínky pro pilotního tenanta a případné zvýhodnění partnerů `Certified Partner SUB`.
- [ ] Pravidla změny tarifu, výpovědi, exportu a výmazu dat po ukončení (vazba na `licencni-podminky-osnova.md`).

Každé rozhodnutí se zapisuje přes `mutation_confirm` v `Decisions`; do té doby se žádné číslo nezveřejňuje na webu, v nabídce ani v komunikaci se zákazníky.
