# Právní a normová báze: pravidla a registr otevřených bodů — Polarita s.r.o. (Verze 2.8)

Tento dokument stanoví, **jak firma zachází s právními předpisy, technickými normami a smlouvami**, a eviduje technické údaje návrhu, které byly ověřeny nebo na ověření čekají. Návrh je teoretický koncept a návod pro čistý stroj; nic v něm nenahrazuje právní ani odborné posouzení.

---

## 1. Zásada: návod neobsahuje čísla předpisů ani označení norem

1. **V celém návodu nejsou čísla zákonů, vyhlášek a nařízení, čísla paragrafů a článků ani označení a edice technických norem.** Návod popisuje jen oblasti (například „pracovněprávní předpisy“, „platná norma pro rozváděče nízkého napětí“) a postup. Nemůže předjímat, jaké předpisy, normy a smlouvy budou platit v době, kdy firma vznikne, ani později.
2. **Předpisy, normy a smlouvy se stahují, studují a používají až po nasazení systému**, z úředních zdrojů a podle skutečné potřeby. Žádný `ai` agent ani člověk nesmí citovat předpis nebo normu zpaměti ani podle tohoto návodu — jen podle záznamu v bázi.
3. **Lhůty, limity a částky uvedené v návodu jsou výchozí orientační hodnoty** (například počet hodin u dohod, délka fikce doručení, doba platnosti zkoušek a oprávnění nebo připravenost případné elektronické evidence tržeb, pokud ji česká legislativa zavede a stanoví datum účinnosti). Platnou hodnotu určuje živá báze ve `Vaultu` od `Bloku 8`: po jejím načtení se výchozí hodnoty porovnají a každý rozdíl se opraví v konfiguraci systému postupem podle kapitoly 5.
4. Zásadu hlídá kontrola konzistence [`nastroje/check_consistency.py`](./nastroje/check_consistency.py): číslo předpisu, paragrafu nebo označení normy v dokumentu je chyba, která zastaví commit.

## 2. Co je právní a normová báze

Báze je řízená část sdílené paměti `Vault`, která vzniká až na běžícím systému:

| Část | Umístění ve `Vault` | Obsah | Odpovídá |
| :--- | :--- | :--- | :--- |
| **Právní báze** | `04-Pravo-a-Smlouvy/` | Platná znění předpisů, které firma skutečně používá, vzory smluv a směrnic sestavené podle nich a uzavřené smlouvy s jejich lhůtami | `15001 pravni-specialista` |
| **Normová báze** | `03-Normy-a-Metodiky/` | Metodické karty platných norem pořízené v rozsahu licence, registr platnosti a souběhu edic | `15002 normovac` |

Každý záznam báze má povinně: úřední název a označení, **zdroj** (úřední místo, odkud byl pořízen), **datum znění nebo účinnosti**, **datum poslední kontroly**, odpovědného `ai`, stav (`platné` / `souběh` / `zrušené`) a **seznam dotčených výstupů** (šablony, směrnice, pojistky orchestrátoru, scénáře `Eval Suite`, školení, ceník). Záznam bez zdroje a data se nesmí použít.

## 3. Kdy a jak báze vzniká

1. **Před nasazením se nestahuje nic.** V `Bloku 0` se pouze zřídí přístupy ke zdrojům (například předplatné norem) a člověk s advokátem připraví nezbytné smlouvy pro den založení firmy.
2. **Prvotní načtení proběhne v `Bloku 8`**, jakmile běží `Vault`. `15001` a `15002` načtou jen to, co potřebuje první skutečná činnost firmy, a ke každému záznamu doplní zdroj a datum. Výchozí hodnoty z návodu porovnají s načteným zněním.
3. **Báze roste podle potřeby.** Nový druh zakázky, dokumentu nebo kontroly nejprve vyvolá doplnění báze. Chybí-li potřebný záznam, práce se zastaví ve stavu `VYŽADUJE NAČTENÍ DO BÁZE` a čeká na jeho pořízení a schválení; odhad ani citace zpaměti nejsou přípustné.
4. **Zdroje jsou jen úřední nebo licencované:** úřední sbírka předpisů, úřední věstník pro normy, placený přístup k normám v rozsahu jeho licence, úřední databáze předpisů EU a registry státní správy. Rozsah, v jakém licence dovoluje výtahy z norem ukládat a zpracovávat, ověří `15002` s `15001` před prvním načtením.
5. **Smlouvy:** šablony balíčku `S1` jsou ukázkové vzory generátoru bez odkazů na předpisy. Skutečné znění každé smlouvy a směrnice sestaví `15001` z báze a před prvním použitím je zreviduje advokát.

## 4. Pravidelné hlídání a aktualizace

| Co | Kdo | Jak často | Výstup |
| :--- | :--- | :--- | :--- |
| Změny předpisů zařazených v bázi | `15001 pravni-specialista` | týdně | záznam o kontrole u každého předpisu; při změně nález podle kapitoly 5 |
| Nové, změněné a zrušené normy | `15002 normovac` | měsíčně po vydání úředního věstníku | aktualizovaný registr platnosti a souběhu edic; při změně nález |
| Vzory smluv, směrnice a informační doložky | `15001` + advokát | nejméně jednou ročně a při každém nálezu | potvrzení platnosti nebo nové znění |
| Uzavřené smlouvy (doba trvání, výpovědní lhůty, indexace, pojistky) | `15001`, `16002 tajemnik` | průběžně v Centrálním Lhůtníku | upozornění před uplynutím lhůty |
| Výchozí hodnoty lhůt a limitů v konfiguraci | `15001`, `15002`, `18001 personalista` | při každém nálezu a jednou ročně | shoda konfigurace s bází |
| Úplnost a stáří báze | `17004 klicnik` | měsíčně | seznam záznamů bez kontroly v řádné lhůtě; takový záznam se označí `PO LHŮTĚ KONTROLY` |

Všechny tyto úkoly jsou položkami Centrálního Lhůtníku. Záznam ve stavu `PO LHŮTĚ KONTROLY` nebo `zrušené` nesmí být podkladem žádného výstupu, dokud ho odpovědný `ai` neprověří.

## 5. Postup při změně předpisu, normy nebo smlouvy

1. **Nález:** odpovědný `ai` zapíše změnu do báze (co se mění, odkdy, zdroj) a založí téma v `Zulip`.
2. **Posouzení dopadu:** ze seznamu dotčených výstupů určí, které šablony, směrnice, pojistky, scénáře `Eval Suite`, školení, ceník a běžící zakázky se musí změnit a do kdy.
3. **Návrh úprav:** připraví změny jako koncept `DRAFT`; nic nenasazuje sám.
4. **Schválení:** jednatel `1001` rozhodne v `Decisions` (`mutation_confirm`); u smluv a směrnic po vyjádření advokáta.
5. **Provedení a ověření:** změny se nasadí, proběhne regresní běh `Eval Suite` a k záznamu báze se zapíše datum kontroly.
6. **Informování:** dotčená oddělení dostanou shrnutí; změna s dopadem na zaměstnance nebo zákazníky se jim oznámí předepsaným způsobem.

## 6. Přejímací podmínka

Ostrý start (`Blok 12`, `Go-Live Gate`) je možný jen tehdy, když báze obsahuje záznamy pro všechny činnosti zahajované prvním dnem provozu, každý záznam má zdroj a datum, výchozí hodnoty lhůt a limitů jsou s bází porovnány a pravidelné kontroly podle kapitoly 4 jsou založeny v Centrálním Lhůtníku.

---

## 7. Technické údaje ověřené při přípravě návrhu

| ID | Údaj | Stav | Zdroj a datum |
| :--- | :--- | :--- | :--- |
| `V-01` | Licence knihoven pro zpracování zvuku: `Silero VAD` = `MIT`, `librosa` = `ISC` | ověřeno a opraveno ve všech dokumentech | metadata balíků, 14. 11. 2026 |
| `V-02` | Elektro autorizace `ČKAIT` mají kanonická označení `IE02` a `TE03` (opraveno proti původně mylně uváděným jednoznakovým kódům oboru) | ověřeno a opraveno ve všech dokumentech | přehled autorizací `ČKAIT`, 14. 11. 2026 |
| `V-03` | Názvy operací webové služby ISDS pro výpis a stažení zpráv | ověřeno a opraveno | informace pro vývojáře ISDS, 14. 11. 2026 |
| `V-04` | Produkční adresa webové služby ISDS | ověřeno a opraveno | informace pro vývojáře ISDS, 14. 11. 2026 |
| `V-17` | Poštovní klient `Mozilla Thunderbird` nepodporuje protokol `JMAP`; ke `Stalwart Mail` se připojuje přes `IMAP IDLE` a `SMTP` | ověřeno a opraveno | plán vývoje klienta, 15. 11. 2026 |
| `V-22` | Existence a licence nástrojů `Nod`, `CadCraft`, `Draivix/aigiscode`, `claude-powerline-rust` a `Draivix/codex-runner` | ověřena jen existence a licence | veřejné repozitáře, 15. 11. 2026 |

## 8. Otevřené body

| ID | Bod | Kde se používá | Kdo rozhodne nebo ověří |
| :--- | :--- | :--- | :--- |
| `N-10` | Funkce, které návrh připisuje nástrojům z `V-22`, nejsou jejich veřejnými popisy potvrzeny (provoz nástroje `Nod` bez dalšího kontejnerového běhového prostředí a s vypnutou telemetrií; doménová pravidla v `aigiscode`; souhrn stropu rozpočtu napříč 20 `ai`; izolace pracovních stromů). Jde o vlastní nadstavbu návrhu, která musí vzniknout vlastním vývojem. | `software/07`, `software/10` | `17001 programator` před nasazením |
| `N-15` | Rozsah, v jakém licence placeného přístupu k normám dovoluje ukládat výtahy do `Vault` a zpracovávat je jazykovým modelem | kapitola 3, karta `15002` | `15002 normovac` + `15001 pravni-specialista` |
| `N-16` | Konfigurace statické pečeti `OpenBao` (`seal "static"`): vyžaduje povinný `current_key_id`, odebrání/odpojení surového pečetního klíče z běžícího kontejneru ihned po odemčení (jinak by kompromitace kontejneru či příkaz `SEAL` umožnily samo-odemčení při restartu) a ujasnění, zda `OpenBao` při `seal "static"` vydává i podíly `Shamir Recovery Keys` (jinak je jedinou cestou obnovy PGP kopie statického klíče v obálce `Break-Glass` a zmínky o podílech se z návodu vypustí). | `software/04`, `README`, kniha `00`, `oddeleni/11`, `oddeleni/17`, karta `17004`, šablona `06b-protokol-break-glass` balíčku `S1` | `17004 klicnik` + `17003 spravce-site` při stavbě `Bloku 4` |
| `R-01` | Ceny, hodinové sazby, přirážky, minimální marže, stupně provize, sazby DPH (`21 %` / `12 %`) a sezónní koeficienty v [`cenik.json`](./balicky/S3-konfigurator-a-tarify/cenik.json); veřejný konfigurátor čte výhradně výřez `public_price_list` (bez interních sazeb, marží a provizí). | balíček `S3` | **Rozhodnuto 15. 11. 2026:** jednatel `1001` schválil znění návrhu beze změn; porovnání s trhem a zápis do `Decisions` proběhne při založení firmy (`Blok 15`). |
| `R-02` | Ceník a kauce půjčovny měřidel | [`balicky/S4-dilensky-terminal-a-pujcovna/README.md`](./balicky/S4-dilensky-terminal-a-pujcovna/README.md) | jednatel `1001` |
| `R-03` | Poskytovatel a úrovně elektronického podpisu; parametry eskalace hlasové recepční | [`balicky/S5-podpis-a-hlasova-recepcni/README.md`](./balicky/S5-podpis-a-hlasova-recepcni/README.md) | jednatel `1001` |
| `R-04` | Kritéria a prahy brány `Go / No-Go`; ceny a limity tarifů SaaS | [`balicky/S7-polarita-elektro-cloud/README.md`](./balicky/S7-polarita-elektro-cloud/README.md) | jednatel `1001` |
| `R-05` | Názvy kanálů `Zulip` `#12-marketing` až `#16-finance-a-kancelar` | `README`, `software/07` | jednatel `1001` |

Právní a normové otázky (například platnost smluvních ujednání, režim pokut, harmonizace norem, počítání lhůt) se v tomto registru nevedou: vznikají a řeší se až nad bází na běžícím systému a rozhoduje o nich advokát nebo odborně způsobilá osoba.
