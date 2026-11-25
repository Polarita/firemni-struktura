# Brána `Go / No-Go` Strategické Etapy III — Polarita Elektro Cloud · Blok 19 (S7) · Verze 3.25

Tento dokument stanoví objektivní spouštěč `Bloku 19`. Doplňuje řídicí dokument [`README.md`](README.md) (kapitola 2, pravidlo 1). Dokud protokol v kapitole 4 nenese verdikt `GO` a podpis `1001`, Blok 19 se nespouští. Brána ve Verzi 3.25 **nebyla měřena** — měření vyžaduje údaje z ostrého provozu po převzetí správcem.

---

## 1. Kritéria brány

Všech pět kritérií musí platit současně ke dni měření. Prahové hodnoty pocházejí ze zadání balíčku `S7` v `03-NAVRHY-BALICKU-NA-POZDEJI.md` a `ai` je nesmí měnit.

| # | Kritérium | Prahová hodnota | Zdroj měření v systému | Data připraví | Nezávisle potvrzuje |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `G1` | Bezchybný interní provoz na `polarita-hq` | **12–18 měsíců** souvislého provozu od `12/12 PASS` Go-Live Gate (`Blok 12`); nejdříve po 12 měsících | Protokol Go-Live Gate a protokoly týdenních testů obnovy a čtvrtletních `Full DR Drill` ve Vaultu `07-IT-a-Architektura`; historie incidentů v `Checkmk Raw` | `17003` `spravce-site` | `17004` `klicnik` |
| `G2` | Aktivně spravované objekty SVJ / B2B v Digitální knize objektu | **≥ 100** objektů | Počet aktivních objektů v `centralni-lhutnik-a-objekty` (`db_erp_lhutnik`) spárovaných s platnou fakturací (`finance-uol-marze-engine`) a smluvním vztahem | `14005` `zakazky` + `16001` `ucetni` | `15001` `pravni-specialista` + `17005` `ai-provoz` |
| `G3` | Vydané revizní zprávy / Výrobní pasy rozváděčů | **≥ 500** vydaných dokumentů (v součtu) | Evidence vydaných dokumentů `cad-urs-engine` ověřená proti podepsaným PDF v `legal-archive`; koncepty (`DRAFT`) se nepočítají | `14003` `revizak` | `15002` `normovac` |
| `G4` | Stabilní skóre `Eval Suite` | **100 %** | Historie běhů `Eval Suite` z `balicky/S2-eval-suite` a `/srv/polarita/workspace/ai-finops/eval-suite/` (`Stage 2`, běh každé 1. pondělí v měsíci) | `17005` `ai-provoz` | `17004` `klicnik` |
| `G5` | Aktivní regionální partneři `Certified Partner SUB` | **≥ 15** partnerů | Partnerský provizní ledger (`finance-uol-marze-engine`) a evidence certifikací v `portal-spolupracovniku` | `16001` `ucetni` | `15001` `pravni-specialista` |

Měří se výhradně agregované počty; do protokolu ani do Vaultu se nezapisují osobní údaje (`0` PII).

---

## 2. Upřesnění pojmů k rozhodnutí

Zadání stanoví prahové hodnoty, ale ne přesné definice níže. Dokud je `1001` neschválí, platí jako `NÁVRH — ke schválení 1001` a protokol je bez nich neúplný.

| Pojem | Návrh definice | Stav |
| :--- | :--- | :--- |
| „Bezchybný provoz“ (`G1`) | Ve sledovaném období žádná ztráta dat, žádný neúspěšný test obnovy ani `Full DR Drill` a žádný bezpečnostní incident s únikem údajů; hranice přípustné nedostupnosti je k doplnění | `NÁVRH — ke schválení 1001` |
| Přesná délka v pásmu 12–18 měsíců (`G1`) | Minimum 12 měsíců; o případném prodloužení až na 18 měsíců rozhodne `1001` podle průběhu provozu | `NÁVRH — ke schválení 1001` |
| „Aktivně spravovaný objekt“ (`G2`) | Objekt s platným smluvním vztahem a alespoň jednou sledovanou lhůtou v Centrálním Lhůtníku | `NÁVRH — ke schválení 1001` |
| „Vydaný“ dokument (`G3`) | Dokument podepsaný oprávněnou fyzickou osobou a uložený v `legal-archive`; kladné i záporné revizní zprávy se počítají stejně | `NÁVRH — ke schválení 1001` |
| „Stabilní“ `100 %` (`G4`) | `100 %` ve všech měsíčních bězích `Stage 2` po dobu sledovaného okna; délka okna je k doplnění | `NÁVRH — ke schválení 1001` |
| Rozsah sady pro `G4` | Základní sada 20 chytáků (`ES-001`–`ES-020`), nebo rozšířená sada 157 scénářů z balíčku `S2`, je-li `Blok 14` nasazen | `NÁVRH — ke schválení 1001` |
| „Aktivní“ partner (`G5`) | Partner s platnou certifikací z Elektro Akademie, platnou pojistkou `≥ 5 mil. Kč` a alespoň jednou zakázkou nebo provizí ve sledovaném období; délka období je k doplnění | `NÁVRH — ke schválení 1001` |
| Stáří měření při podpisu | Nejvyšší přípustné stáří měření ke dni podpisu `1001` | `NÁVRH — ke schválení 1001` |

---

## 3. Postup měření a rozhodnutí

1. Měření zahajuje `11001 ceo` na pokyn `1001`, nejdříve 12 měsíců po `12/12 PASS` Go-Live Gate (viz Prompt 1 v `README.md`).
2. Každé kritérium změří `ai` zaměstnanec ze sloupce „Data připraví“ a uvede zdroj, datum a opakovatelný postup. Chybí-li zdroj, zapíše se `NEZMĚŘENO` — hodnota se nikdy neodhaduje.
3. Nezávislou kontrolu provede `ai` zaměstnanec ze sloupce „Nezávisle potvrzuje“ (vzor `Worker / Judge`: dostává zadání, hodnotu a postup měření, nikoli úvahy toho, kdo měřil).
4. `11001 ceo` sestaví koncept protokolu (`DRAFT`) a vloží jej do `Decisions`.
5. **Verdikt:** `GO` lze navrhnout jen při splnění všech pěti kritérií. Jediné nesplněné nebo `NEZMĚŘENO` kritérium znamená `NO-GO`. Kritéria se nesčítají, nekompenzují ani nezaokrouhlují.
6. **Rozhodnutí patří výhradně `1001`:** `GO` nabývá platnosti až jeho podpisem protokolu (`mutation_confirm` v `Decisions` + podepsané PDF uložené v `legal-archive`). `1001` může rozhodnout `NO-GO` i při splnění všech kritérií (například z obchodních nebo kapacitních důvodů); opačně to neplatí — nesplněnou bránu nelze podpisem přehlasovat bez změny tohoto dokumentu.
7. Při `NO-GO` se zapíše, co chybí; nové měření se spouští až na další pokyn `1001`.

**Doplňkové podmínky připravenosti (`NÁVRH — ke schválení 1001`, nejsou součástí pěti závazných kritérií a nepodmiňují verdikt `GO`):** do protokolu se zapisuje jen jejich stav — rozpracovanost konceptu (`DRAFT`) licenčních podmínek a zpracovatelské smlouvy, rozpracovanost návrhu tarifů, pojistné krytí odpovídající poskytování softwaru třetím stranám a kapacita lidí pro zákaznickou podporu. Revize podmínek advokátem a schválení tarifů `1001` následují až po podpisu `GO` (Prompt 3 v `README.md`) a jsou podmínkou založení pilotního tenanta, nikoli podmínkou `GO`; před `GO` se smějí jen udržovat koncepty v této složce.

---

## 4. Rozhodovací protokol (vzor k vyplnění)

```text
PROTOKOL BRÁNY GO / NO-GO — STRATEGICKÁ ETAPA III (BLOK 19, POLARITA ELEKTRO CLOUD)

Společnost:            Polarita s.r.o., IČO 14180324
Datum měření:          ____________________
Sledované období:      od ____________ do ____________
Datum 12/12 PASS Go-Live Gate (Blok 12): ____________________
Protokol sestavil:     11001 ceo (koncept DRAFT)

KRITÉRIUM                                   PRÁH             NAMĚŘENO     ZDROJ / ODKAZ NA DŮKAZ     SPLNĚNO (ANO / NE / NEZMĚŘENO)
G1 Bezchybný interní provoz                 12–18 měsíců     __________   ________________________   ______
G2 Aktivně spravované objekty               >= 100           __________   ________________________   ______
G3 Vydané revizní zprávy / pasy rozváděčů   >= 500           __________   ________________________   ______
G4 Skóre Eval Suite (stabilně)              100 %            __________   ________________________   ______
G5 Aktivní Certified Partner SUB            >= 15            __________   ________________________   ______

Použité definice pojmů (kapitola 2), verze schválená 1001 dne: ____________________

Nezávislá kontrola měření:
  G1, G4 — 17004 klicnik:                        SOUHLASÍ / NESOUHLASÍ   poznámka: ____________________
  G2     — 15001 pravni-spec. + 17005 ai-prov.: SOUHLASÍ / NESOUHLASÍ   poznámka: ____________________
  G3     — 15002 normovac:            SOUHLASÍ / NESOUHLASÍ   poznámka: ____________________
  G5     — 15001 pravni-specialista:  SOUHLASÍ / NESOUHLASÍ   poznámka: ____________________

Doplňkové podmínky připravenosti (jen stav, nepodmiňují GO): ____________________

NÁVRH VERDIKTU (11001 ceo):   GO / NO-GO
Chybí ke splnění (při NO-GO): ________________________________________

ROZHODNUTÍ JEDNATELE
Verdikt:      GO / NO-GO
Odůvodnění:   ________________________________________
Podpis:       Václav Šercl, jednatel (1001 / STAT-1001)
Datum:        ____________________
Způsob:       mutation_confirm v Decisions + podepsané PDF v legal-archive
```

Bez vyplněného a podepsaného oddílu „Rozhodnutí jednatele“ s verdiktem `GO` je brána uzavřena.
