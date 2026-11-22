# Protokol o aktivaci a ukončení režimu Break-Glass
**Spis:** {{spis_id}}

**Číslo protokolu:** {{cislo_protokolu}} · **Navazuje na plnou moc č.:** {{cislo_plne_moci}}

Společnost: **Polarita s.r.o.**, se sídlem Na Folimance 2155/15, Vinohrady, 120 00 Praha 2, IČO 14180324, DIČ CZ14180324, zapsaná v obchodním rejstříku vedeném Městským soudem v Praze pod sp. zn. C 361683, datová schránka w9bbdva, jednatel Václav Šercl.

Protokol dokládá, kdy a proč byl aktivován nouzový režim zastupování nedostupného jednatele, jaké prostředky byly zástupci předány, v jakém režimu běžela Podatelna ISDS, které úkony byly za společnost učiněny a jak byl režim ukončen. Do protokolu se nikdy nezapisují hesla, kódy PIN, statický pečetní klíč (`seal "static"`), záchranné podíly `Shamir`, obnovovací klíče ani obsah zapečetěné obálky.

## Část A — Aktivace režimu

| Položka | Údaj |
| :--- | :--- |
| Datum a čas aktivace | {{datum_cas_aktivace}} |
| Důvod aktivace | {{duvod_aktivace}} |
| Způsob aktivace (pokyn jednatele / zápis při nedostupnosti) | {{zpusob_aktivace}} |
| Způsob ověření nedostupnosti jednatele | {{zpusob_overeni_nedostupnosti}} |
| Předpokládaná doba nedostupnosti | {{predpokladana_doba_nedostupnosti}} |
| Režim aktivoval (jméno a funkce) | {{aktivoval_jmeno}}, {{aktivoval_funkce}} |
| Zástupce v režimu Break-Glass | {{jmeno_zastupce}} |
| Osobní číslo zástupce | {{osobni_cislo}} |
| Role zástupce | {{role_zastupce}} |
| Svědek aktivace | {{svedek_aktivace}} |

Zástupce potvrzuje, že se seznámil s rozsahem i omezeními nouzové plné moci a že bude za společnost činit pouze úkony, které plná moc výslovně připouští.

## Část B — Předané prostředky

| Č. | Prostředek | Identifikace | Stav při předání | Datum a čas předání |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Zapečetěná obálka Break-Glass | pečeť č. {{cislo_peceti_obalky}} | {{stav_peceti_pri_predani}} | {{obalka_cas_predani}} |
| 2 | Originál nouzové plné moci | č. {{cislo_plne_moci}} | {{plna_moc_stav_predani}} | {{plna_moc_cas_predani}} |
| 3 | Další předané prostředky | {{dalsi_predane_prostredky}} | {{dalsi_prostredky_stav_predani}} | {{dalsi_prostredky_cas_predani}} |

Obálka byla otevřena: {{obalka_otevrena}}. Důvod otevření a rozsah použitého obsahu: {{duvod_otevreni_obalky}}

**Záložní YubiKey č. 2 se nepředává.** Je výhradně osobní náhradou jednatele a zůstává v samostatné zapečetěné obálce v trezoru. Protokol eviduje pouze kontrolu neporušenosti její pečeti:

| Položka | Údaj |
| :--- | :--- |
| Pečeť obálky se záložním YubiKey č. 2 | č. {{cislo_peceti_obalky_yubikey_2}} |
| Stav pečeti při aktivaci | {{stav_peceti_obalky_yubikey_2}} |
| Datum a čas kontroly | {{kontrola_peceti_yubikey_2_cas}} |

Zástupce se ve schvalovací frontě Decisions přihlašuje vlastním účtem a vlastním hardwarovým klíčem; oprávnění k potvrzování je aktivní jen po dobu režimu a jen pro třídy úkonů vyjmenované v plné moci.

| Položka | Údaj |
| :--- | :--- |
| Vlastní hardwarový klíč zástupce | {{vlastni_hardwarovy_klic}} |
| Aktivace oprávnění k potvrzování v Decisions | {{aktivace_opravneni_decisions}} |

Hlavní YubiKey jednatele, záložní YubiKey č. 2, osobní kvalifikovaný elektronický podpis jednatele a jeho přístupové údaje se zástupci nepředávají.

## Část C — Stav Podatelny ISDS (datová schránka w9bbdva)

Po dobu režimu běží Podatelna ISDS v jednom ze dvou stavů:

1. **ŘÍZENÉ VYZVEDÁVÁNÍ** — zprávy vyzvedává pověřený zástupce přítomný v provozu, v pracovní dny v čase stanoveném provozním řádem Podatelny. Přihlášením osoby, která má přístup k dodané zprávě, je zpráva doručena (doručení přihlášením podle předpisů o datových schránkách) a běží od něj lhůty.
2. **PAUSED** — v neobsazené nepřítomnosti je automatické dotazování datové schránky pozastaveno, do schránky se nikdo nepřihlašuje a sledují se pouze externí oznámení o dodání zprávy. U každé dodané zprávy se hlídá den, kdy nastane fikce doručení: nepřihlásí-li se do schránky osoba s přístupem k dodané zprávě do 10 dnů ode dne dodání, považuje se zpráva za doručenou posledním dnem této lhůty (fikce doručení podle předpisů o datových schránkách).

| Položka | Údaj |
| :--- | :--- |
| Stav Podatelny ISDS po aktivaci | {{rezim_isds}} |
| Datum a čas přepnutí do tohoto stavu | {{datum_cas_prepnuti_isds}} |
| Pověřený zástupce pro vyzvedávání (při řízeném vyzvedávání) | {{povereny_zastupce_isds}} |
| Změny stavu v průběhu režimu | {{zmeny_rezimu_isds}} |

Přehled zpráv dodaných do datové schránky v průběhu režimu:

| Č. | Dodáno dne | Odesílatel | Poslední den lhůty (fikce doručení) | Vyzvednuto dne / stav | Spis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | {{isds_zprava_1_dodano}} | {{isds_zprava_1_odesilatel}} | {{isds_zprava_1_fikce}} | {{isds_zprava_1_stav}} | {{isds_zprava_1_spis}} |
| 2 | {{isds_zprava_2_dodano}} | {{isds_zprava_2_odesilatel}} | {{isds_zprava_2_fikce}} | {{isds_zprava_2_stav}} | {{isds_zprava_2_spis}} |
| 3 | {{isds_zprava_3_dodano}} | {{isds_zprava_3_odesilatel}} | {{isds_zprava_3_fikce}} | {{isds_zprava_3_stav}} | {{isds_zprava_3_spis}} |

Datové zprávy odeslané po dobu režimu: {{odeslane_datove_zpravy}}

Odeslat datovou zprávu smí v režimu Break-Glass výhradně jmenovaný bankovní zmocněnec nebo prokurista, a to vlastním přístupem pověřené osoby s oprávněním odesílat, po kladném posouzení podání právní specialistkou (15001) a po potvrzení vlastním hardwarovým klíčem v Decisions. Zástupný revizní technik datové zprávy neodesílá. Mimo režim Break-Glass odesílá jen jednatel.

## Část D — Seznam provedených úkonů

Zapisuje se každý úkon učiněný za společnost, a to bez zbytečného odkladu po jeho provedení. Každé vyzvednutí datové zprávy uvedené v části C je samostatným úkonem; u úkonu potvrzeného v Decisions se uvede i třída potvrzení.

| Č. | Datum a čas | Úkon | Spis | Opora v plné moci | Provedl |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | {{ukon_1_cas}} | {{ukon_1_popis}} | {{ukon_1_spis}} | {{ukon_1_opora}} | {{ukon_1_provedl}} |
| 2 | {{ukon_2_cas}} | {{ukon_2_popis}} | {{ukon_2_spis}} | {{ukon_2_opora}} | {{ukon_2_provedl}} |
| 3 | {{ukon_3_cas}} | {{ukon_3_popis}} | {{ukon_3_spis}} | {{ukon_3_opora}} | {{ukon_3_provedl}} |
| 4 | {{ukon_4_cas}} | {{ukon_4_popis}} | {{ukon_4_spis}} | {{ukon_4_opora}} | {{ukon_4_provedl}} |
| 5 | {{ukon_5_cas}} | {{ukon_5_popis}} | {{ukon_5_spis}} | {{ukon_5_opora}} | {{ukon_5_provedl}} |
| 6 | {{ukon_6_cas}} | {{ukon_6_popis}} | {{ukon_6_spis}} | {{ukon_6_opora}} | {{ukon_6_provedl}} |

Úkony, které zástupce odmítl provést, protože přesahovaly rozsah plné moci, a způsob jejich odložení: {{odmitnute_ukony}}

Položky schvalovací fronty Decisions, které nepatří do tříd úkonů povolených plnou mocí, zůstaly po dobu režimu pozastaveny a čekají na jednatele: {{pozastavene_polozky_decisions}}

## Část E — Ukončení režimu

| Položka | Údaj |
| :--- | :--- |
| Datum a čas ukončení | {{datum_cas_ukonceni}} |
| Důvod ukončení | {{duvod_ukonceni}} |
| Režim ukončil | {{ukoncil_jmeno}} |
| Celková doba trvání režimu | {{doba_trvani_rezimu}} |
| Písemnosti a zásilky předané jednateli | {{predane_pisemnosti}} |

## Část F — Vrácení prostředků a rotace klíčů

| Č. | Krok | Výsledek | Datum a čas |
| :--- | :--- | :--- | :--- |
| 1 | Kontrola neporušenosti pečeti obálky se záložním YubiKey č. 2 (klíč se nepředával) | {{kontrola_peceti_yubikey_2_ukonceni}} | {{kontrola_peceti_yubikey_2_ukonceni_cas}} |
| 2 | Kontrola a nové zapečetění obálky Break-Glass (nová pečeť č. {{cislo_nove_peceti}}) | {{nove_zapeceteni_obalky}} | {{nove_zapeceteni_cas}} |
| 3 | Rotace tajemství a přístupových klíčů dotčených režimem v trezoru OpenBao | {{rotace_tajemstvi}} | {{rotace_tajemstvi_cas}} |
| 4 | Zneplatnění dočasných přístupů a relací zástupce a vypnutí jeho oprávnění k potvrzování v Decisions | {{zneplatneni_pristupu}} | {{zneplatneni_pristupu_cas}} |
| 5 | Zrušení pověření zástupce v datové schránce w9bbdva | {{zruseni_povereni_isds}} | {{zruseni_povereni_isds_cas}} |
| 6 | Obnovení běžného provozu Podatelny ISDS | {{obnoveni_podatelny_isds}} | {{obnoveni_podatelny_isds_cas}} |

Rotaci připravil a její úplnost zkontroloval: {{rotaci_zkontroloval}}

## Část G — Zpětná kontrola jednatelem

Jednatel po návratu zkontroloval všechny úkony uvedené v části D, stav lhůt z datových zpráv uvedených v části C a úplnost kroků v části F.

| Položka | Údaj |
| :--- | :--- |
| Datum zpětné kontroly | {{datum_zpetne_kontroly}} |
| Výsledek kontroly | {{vysledek_zpetne_kontroly}} |
| Zjištění a výhrady | {{zjisteni_zpetne_kontroly}} |
| Uložená nápravná opatření a termíny | {{napravna_opatreni}} |

## Podpisy

Místo a datum: {{misto_podpisu}}, {{datum_podpisu}}

Zástupce v režimu Break-Glass: {{jmeno_zastupce}}

Podpis: ........................................

Jednatel Polarita s.r.o.: Václav Šercl

Podpis: ........................................
