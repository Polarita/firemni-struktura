# Blok 15 · Balíček S3 — Interaktivní konfigurátor balíčků na klíč a GTM kniha tarifů MRR · Verze 3.28

Tento dokument je řídicím dokumentem **`Bloku 15`** Rozvojové Etapy II společnosti **Polarita s.r.o.** Balíček rozšiřuje základní ceník z `Bloku 0` a `Bloku 9` o **jediný verzovaný zdroj cen** ([`cenik.json`](./cenik.json)), deterministické **cenové jádro** ([`pricing.py`](./pricing.py)), **interaktivní konfigurátor** paušálu „Elektro Správa SVJ a Firem“ ([`konfigurator.html`](./konfigurator.html)), obchodní **knihu tarifů MRR** ([`kniha-tarifu-mrr.md`](./kniha-tarifu-mrr.md)) a interní **kalkulační a provizní matici** ([`kalkulacni-matice.md`](./kalkulacni-matice.md)). Nepřidává žádného `ai` agenta ani databázi.

> **Stav cen: `SCHVÁLENO 1001` (15. 11. 2026).** Výchozí ceník v `cenik.json` schválil jednatel `1001` ve znění návrhu, beze změn (`meta.approved = true`). Hodnoty nebyly porovnány s trhem ani s nákupními ceníky — to je úkol `Promptu 1` při založení firmy, kdy se schválení zároveň zapíše do `Decisions`. Každá další změna ceníku prochází `mutation_confirm`. Konfigurátor zobrazuje výstražný pruh „NÁVRH“ jen při `meta.approved = false`.

---

## 1. Seznam softwaru a modulů

| Oblast | Soubor / modul | Kanál / Režim | Role a použití v Polarita s.r.o. (Verze 3.28) | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Jediný zdroj cen** | [`cenik.json`](./cenik.json) | verzováno v `Gitea`, změna jen přes `mutation_confirm` | 3 tarify MRR, 3 balíčky na klíč s cenou od–do, hodinové zúčtovací sazby, přirážka na materiál, minimální krycí příspěvek, stupně provize partnera a sezónní koeficienty. | `14002` `rozpoctar`, `16001` `ucetni` *(schvaluje `1001`)* |
| **Cenové jádro** | [`pricing.py`](./pricing.py) | čistý `Python` (`Decimal`), bez závislostí | Výpočet měsíčního a ročního paušálu, rozsahu balíčků, ceny práce a materiálu, `Hard-Stop` marže a provize partnera; generuje konfigurátor a přehled cen. Žádný `ai` agent nepočítá ceny zpaměti. | `17001` `programator` *(Judge `16001`)* |
| **Konfigurátor** | [`konfigurator.html`](./konfigurator.html) *(ze šablony [`konfigurator.template.html`](./konfigurator.template.html))* | statická stránka, nic neodesílá | Referenční implementace pro `polarita.cz`, `polarita.eu` a `akademie.polarita.cz`; odkazuje na Kalkulačku rizik a úspor SVJ (`/kalkulacka-svj`, `N6`). | `17002` `webmaster`, `12001` `marketing` |
| **Kniha tarifů** | [`kniha-tarifu-mrr.md`](./kniha-tarifu-mrr.md) | obchodní dokument | Co který tarif obsahuje, pravidla prodeje, indexace a produktizované balíčky na klíč. | `12001` `marketing`, `12002` `obsah-geo` |
| **Kalkulační a provizní matice** | [`kalkulacni-matice.md`](./kalkulacni-matice.md), [`prehled-cen.md`](./prehled-cen.md) *(generováno)* | interní | Pravidla nacenění pro `14002 rozpoctar` a `14005 zakazky`, `Hard-Stop` pod minimální marží a provizní matice `N8` pro `16001 ucetni`. | `14002` `rozpoctar`, `16001` `ucetni` |
| **Testy** | [`test_pricing.py`](./test_pricing.py) | `python -m unittest` | Testy výpočtů, validace ceníku, veřejného výřezu, mezních hodnot a shody konfigurátoru s ceníkem; javascriptové jádro konfigurátoru se porovnává s `pricing.py` v `Node.js` nebo v prohlížeči `Chromium` (bez obojího se tento jeden test přeskočí). | `17004` `klicnik` |

---

## 2. Architektonická pravidla a zdůvodnění

1. **Jeden zdroj, žádné opisování čísel:**
   * Ceny žijí pouze v `cenik.json`. Konfigurátor i přehled cen se z něj generují příkazem `python pricing.py --build`; test hlídá, že vygenerované soubory odpovídají aktuálnímu ceníku.
   * Dokumenty v Markdownu čísla neopisují — odkazují na generovaný [`prehled-cen.md`](./prehled-cen.md).
2. **Férový firemní tarif bez trestu za růst:**
   * Paušál se počítá z počtu objektů a dalších vchodů. Neexistuje příplatek za člena výboru SVJ ani za uživatele portálu.
3. **`Hard-Stop` pod minimální marží:**
   * Nabídka s krycím příspěvkem pod minimem z ceníku se bez podpisu `1001` neodešle (`offer_margin_check` vrací `hard_stop = true`; pravidlo `MARGIN_HARD_STOP` v sadě `S2`).
   * Minimální marže se hodnotí **za celou nabídku** (práce + materiál dohromady), ne po řádcích. Čistě materiálová dodávka se touto maticí nenabízí — jde přes ceník e-shopu — a `offer_margin_check` ji odmítne.
   * Závazná nabídka vyžaduje ceník schválený `1001` a ke dni nabídky už účinný (`meta.valid_from` nejpozději v den nabídky, `meta.approved_on` ne později než `meta.valid_from`, obojí skutečná kalendářní data); schválený, ale dosud neúčinný ceník `offer_margin_check` odmítne. Marže se počítá nad zaokrouhlenými částkami, které v nabídce skutečně stojí.
   * Ceník má doménové meze (částka nejvýše `100 000 000 Kč`, sezónní koeficient nejvýše `10`) a validace navíc odmítne ceník, u něhož by veřejný konfigurátor při největším povoleném rozsahu nespočítal mezivýsledek přesně v celých haléřích. Veřejná stránka dostává částky z `pricing.py` už jako celá čísla a výpočet mimo přesný rozsah zastaví, místo aby jej potichu zaokrouhlila.
4. **Konfigurátor není nabídka:**
   * Stránka nic neodesílá ani neukládá, neobsahuje formulář s osobními údaji a výslovně uvádí, že závaznou nabídku připraví a potvrdí člověk. Závazná cenová nabídka jde vždy přes `Decisions`.
5. **Vazba na ostatní balíčky a bloky:**
   * Smluvní texty tarifů řeší sestava č. 2 balíčku `S1` (paušální servisní smlouva MRR), provizní ledger vede `finance-uol-marze-engine` (`Blok 11`), web a e-shop pocházejí z `Bloku 9`.

---

## 3. Pokyny k instalaci a konfiguraci pro `ai` (Prompty)

### Prompt 1 — Ověření ceníku proti trhu, jeho změny a zavedení jediného zdroje cen (`pro 14002 rozpoctar` + `16001 ucetni`)

```text
Ověř výchozí ceník společnosti Polarita s.r.o. (schválený jednatelem 1001 dne 15. 11. 2026 bez porovnání s trhem) a připrav případné změny ke schválení:

1. Projdi hodnoty v balicky/S3-konfigurator-a-tarify/cenik.json (tarify MRR, balíčky na klíč, hodinové zúčtovací sazby, přirážka na materiál, minimální krycí příspěvek, stupně provize, sezónní koeficienty) a porovnej je s živými nákupními ceníky od 13002 nakupci, post-kalkulací zakázek a tržním benchmarkem.
2. Ke každé hodnotě připrav krátké zdůvodnění a případný protinávrh; nic v souboru sám neměň.
3. Zapiš do Decisions výchozí schválení ceníku a předlož jednateli 1001 jeden transakční diff před → po všech navržených změn. Po mutation_confirm zvyš meta.version a nastav meta.approved_on a meta.valid_from; meta.approved a meta.approved_by = "1001" zůstávají.
4. Spusť python pricing.py --build a python -m unittest test_pricing; výsledek musí být OK.
5. Ulož schválený ceník do Gitea a do Vaultu (05-Obchod-a-Ceniky) zapiš pouze odkaz a datum platnosti.
```

### Prompt 2 — Nasazení konfigurátoru na weby (`pro 17002 webmaster` + `12001 marketing`)

```text
Nasaď konfigurátor paušálu Elektro Správa SVJ a Firem na weby Polarita s.r.o.:

1. Převeď referenční stránku konfigurator.html na komponentu webu polarita.cz (Astro + Tailwind CSS) se stejnými vzorci jako v pricing.py; do veřejné stránky předávej výhradně veřejný výřez cenik.json získaný funkcí pricing.public_price_list() (bez interních hodinových sazeb, marží a provizí).
2. Propoj konfigurátor s Kalkulačkou rizik a úspor SVJ (/kalkulacka-svj) a s formulářem poptávky; formulář smí odeslat jen údaje výslovně zadané návštěvníkem a s informací o zpracování osobních údajů podle GDPR.
3. Na polarita.eu a akademie.polarita.cz vlož odkaz na konfigurátor; ceny na třech webech nikdy neudržuj odděleně.
4. Při meta.approved = false stránku nezveřejňuj; pruh NÁVRH se řídí pouze nastavením v ceníku, nikdy úpravou šablony.
5. Měř konverze v Umami bez cookies třetích stran a předej stránku ke kontrole 15001 pravni-specialista (spotřebitelské právo, uvádění cen).
```

### Prompt 3 — Kalkulace zakázek a provizní matice (`pro 14002 rozpoctar`, `14005 zakazky` a `16001 ucetni`)

```text
Zapoj cenové jádro do nacenění zakázek a výpočtu partnerských provizí:

1. Při každé nabídce volej funkce pricing.py (labour_price, material_price, package_range, offer_margin_check); žádnou cenu nepočítej zpaměti. Marži hodnoť funkcí offer_margin_check za celou nabídku (práce + materiál dohromady); čistě materiálovou dodávku touto maticí nenaceňuj, patří do ceníku e-shopu.
2. Vrátí-li offer_margin_check hard_stop = true, nabídku neodesílej a eskaluj ji jednateli 1001 do Decisions s rozpadem nákladů.
3. Jednou měsíčně spočítej funkcí partner_commission trvalou provizi každého Certified Partner SUB z uhrazeného měsíčního MRR přivedených objektů a zapiš ji do Partnerského provizního ledgeru ve finance-uol-marze-engine (výplata až po schválení v Decisions).
4. Sezónní koeficienty používej jen u balíčků na klíč; paušály MRR se indexují jednou ročně dle smlouvy.
5. Odchylku skutečné marže od kalkulace nad 10 % nahlas 11001 ceo a navrhni úpravu ceníku cestou Promptu 1.
```

---

## 4. Ověřitelné podmínky dokončení Bloku 15

- [ ] Ceník je schválen jednatelem `1001` (`meta.approved = true`, vyplněné `approved_by`, `approved_on` a `valid_from`), schválení je zapsáno v `Decisions` a hodnoty jsou porovnány s trhem a nákupními ceníky.
- [ ] `python -m unittest test_pricing` skončí `OK` a `python pricing.py --build` přegeneruje konfigurátor i přehled cen beze změny proti verzovanému stavu.
- [ ] Konfigurátor na `polarita.cz` počítá shodně s `pricing.py` (kontrolní příklad: tarif Standard Objekt, 3 objekty, 4 další vchody) a nevykazuje vodorovný posuv na šířce telefonu.
- [ ] Nabídka pod minimálním krycím příspěvkem je zastavena (`Hard-Stop`) a bez podpisu `1001` ji nelze odeslat.
- [ ] Partnerská provize se počítá z uhrazeného MRR ve stupních uvnitř pásma `10–15 %` a zapisuje do provizního ledgeru.

---

## 5. Stav ve Verzi 3.28

**Hotovo v této složce a ověřeno spuštěním (14. 11. 2026):**

- `cenik.json`, cenové jádro `pricing.py` a testy — všechny skončí `OK`;
- vygenerovaný `konfigurator.html` a `prehled-cen.md`;
- konfigurátor vyzkoušen v prohlížeči: Standard Objekt, 3 objekty, 4 vchody → `12 130 Kč` měsíčně a `145 560 Kč` ročně; 2× EV Wallbox v červenci → `79 800 – 199 500 Kč` (shodné s `pricing.py`); šířka `375 px` bez vodorovného posuvu.

**Rozhodnuto:** jednatel `1001` dne 15. 11. 2026 schválil všechny ceny a sazby ve znění návrhu, beze změn; ceník i generované soubory byly téhož dne znovu sestaveny a testy prošly.

**Vyžaduje živý server:**

- zápis schválení do `Decisions` a porovnání hodnot s trhem a nákupními ceníky (`Prompt 1`);
- převod konfigurátoru do webu `polarita.cz` (`Blok 9`), napojení na poptávkový formulář a `Umami`;
- napojení provizní matice na `finance-uol-marze-engine` (`Blok 11`).

Spuštění: `python pricing.py --build` · `python -m unittest -v test_pricing` · otevřít `konfigurator.html` v prohlížeči.
