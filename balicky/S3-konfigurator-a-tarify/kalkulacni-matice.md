# Interní kalkulační a provizní matice (`N8`) · Verze 3.14

Interní pravidla pro `14002 rozpoctar`, `14005 zakazky`, `12001 marketing` a `16001 ucetni`. Čísla se neopisují — hodnoty jsou v [`cenik.json`](./cenik.json) a v generovaném [`prehled-cen.md`](./prehled-cen.md) (stav `SCHVÁLENO 1001`, 15. 11. 2026); výpočty provádí [`pricing.py`](./pricing.py).

## 1. Skladba ceny zakázky

| Složka | Zdroj hodnoty | Funkce v `pricing.py` | Kdo odpovídá |
| :--- | :--- | :--- | :--- |
| Práce — montér-elektrotechnik, vedoucí elektrotechnik, revizní technik (`TIČR`), projektant elektro | `hourly_rates` | `labour_price` (sleva na práci dle tarifu zákazníka) | `14002` `rozpoctar` |
| Materiál z `Elektro WMS` | živé nákupní ceny od `13002 nakupci` + `material_markup_pct` | `material_price` | `14002` + `13002` |
| Balíček na klíč | `turnkey_packages` (od–do) × `seasonal_coefficients` | `package_range` | `14002` + `12001` |
| Paušál MRR | `mrr_tariffs` | `monthly_fee`, `annual_fee` | `14005` + `16001` |
| Stavební přípomoce (9 vrstev CS ÚRS) | rozpočet `cad-urs-engine` | mimo tento modul | `14002` |

## 2. `Hard-Stop` pod minimální marží

1. Krycí příspěvek se počítá **za celou nabídku** (práce + materiál dohromady), nikdy po jednotlivých řádcích: `(cena nabídky bez DPH − všechny přímé náklady práce i materiálu) / cena nabídky bez DPH`. Výpočet provádí funkce `offer_margin_check`; samotná přirážka na materiál (`material_markup_pct`) je záměrně nižší než minimální marže a dorovnává ji práce.
2. Je-li výsledek pod hodnotou `minimum_contribution_margin_pct`, funkce vrátí `hard_stop = true`; tato hodnota se předává pojistce jako pole `below_minimum_margin`.
3. **Čistě materiálová dodávka** (nabídka bez práce) se touto maticí nenaceňuje a `offer_margin_check` ji odmítne — prodej samotného materiálu jde přes ceník e-shopu.
4. Závaznou nabídku lze počítat jen ze schváleného a ke dni nabídky už účinného ceníku (`meta.approved`, `meta.valid_from` nejpozději v den nabídky); nad neschváleným nebo dosud neúčinným ceníkem `offer_margin_check` skončí chybou. Datum nabídky se předává parametrem `offer_date`, výchozí je dnešní den.
5. Marže se posuzuje nad přesně těmi částkami, které jsou v nabídce: řádek práce i řádek materiálu se zaokrouhlí na haléře, cena nabídky je jejich součet (vrací se jako `price_without_vat`) a vykazovaná marže se zaokrouhluje dolů, takže podlimitní nabídka se nikdy nezobrazí jako vyhovující.
6. Nabídka s `hard_stop = true` se **neodešle**; `14002` ji předloží s rozpadem nákladů jednateli `1001` do `Decisions`. Odeslat ji lze jen po jeho výslovném podpisu výjimky.
7. Pravidlo ověřuje scénář `MARGIN_HARD_STOP` v sadě balíčku `S2`; závazná nabídka bez výsledku kontroly marže tam končí `FAIL_CLOSED`.

## 3. Zádržné a platební podmínky

- Zádržné `5–10 %` (pásmo dané návrhem firmy) hlídá `finance-uol-marze-engine`; konkrétní výše se sjednává ve smlouvě o dílo.
- Upomínkový automat `+3 / +10 / +20 dnů` po splatnosti končí předžalobní výzvou (šablona `S1` č. 7).

## 4. Provizní matice partnerů `Certified Partner SUB` (`N8`)

1. Partner dostává **100 % sjednané ceny realizace** své dílčí objednávky.
2. Navíc mu náleží **trvalá provize z uhrazeného měsíčního paušálu MRR** objektů, které přivedl — v pásmu `10–15 %`. Stupně uvnitř pásma schválené jednatelem `1001` jsou v `partner_commission.tiers`.
3. Provize se počítá funkcí `partner_commission` vždy z **uhrazeného** MRR daného měsíce; neuhrazený nebo dobropisovaný paušál provizi nezakládá.
4. Výpočet zapisuje `16001 ucetni` do Partnerského provizního ledgeru; výplatu schvaluje `1001` v `Decisions` v měsíční uzávěrce.
5. Provize zaniká ukončením paušální smlouvy objektu nebo ukončením partnerské smlouvy podle jejích podmínek (šablona `S1` č. 3).

## 5. Sezónní matice

Sezónní koeficienty (`seasonal_coefficients`) se používají **jen u balíčků na klíč** a pokrývají všech 12 měsíců právě jednou (hlídá test). Paušály MRR sezónnost nemají. Marketing podle nich plánuje kampaně (`12001`), rozpočtář podle nich upravuje rozsah od–do.

## 6. Změna hodnot

Hodnoty se mění výhradně úpravou `cenik.json` přes `mutation_confirm` v `Decisions` → `python pricing.py --build` → `python -m unittest test_pricing`. Ceník se při každém načtení validuje (záporná nebo nečíselná částka, procento mimo `0–100`, cena „od“ nad cenou „do“, měsíc bez sezónního koeficientu nebo se dvěma, nekonzistentní údaje o schválení) a s neplatným ceníkem skončí `pricing.py` chybou. Příkaz `--build` vkládá do veřejného `konfigurator.html` výhradně veřejný výřez (`pricing.public_price_list` bez interních sazeb, marží a provizí). Ruční úprava konfigurátoru nebo přehledu cen je zakázána (test ji odhalí).
