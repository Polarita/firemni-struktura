# Právní a normová báze: pravidla a registr otevřených bodů — Polarita s.r.o. (Verze 3.29)

> V režimu TEST proveď průzkum, ulož plán a automaticky nasaď a ověř změny. Použij testovací data a místní protějšky externích služeb. Skutečné osobní klíče, certifikáty a živé účty zapoj až po uživatelském testu a převzetí správcem. Podrobný postup uvádí [README](./README.md).

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

1. **Blok 0** zaznamená, které produkční přístupy a podklady správce doplní po převzetí. Pro TEST připraví instalátor vzorové podklady sám.
2. **V bloku 8** instalátor založí bázi ve Vaultu a předvede evidenci servisní poptávky na syntetickém spisu. Vzor právního minima spojí se zdrojem, datem znění, datem kontroly, rolí a dotčenými výstupy. Ověří jeho vyhledání a termíny dalších kontrol. **Po převzetí** jednatel `1001` určí skutečné činnosti, `15001` a `15002` doplní potřebné zdroje, porovnají s nimi limity a lhůty a advokát posoudí listiny před prvním produkčním použitím.
3. **Báze roste podle potřeby.** Nový druh zakázky, dokumentu nebo kontroly nejprve vyvolá doplnění báze. Chybí-li potřebný záznam, práce se zastaví ve stavu `VYŽADUJE NAČTENÍ DO BÁZE` a čeká na jeho pořízení a schválení; odhad ani citace zpaměti nejsou přípustné.
4. **Zdroje jsou jen úřední nebo licencované:** úřední sbírka předpisů, úřední věstník pro normy, placený přístup k normám v rozsahu jeho licence, úřední databáze předpisů EU a registry státní správy. V bloku 8 se technicky ověří `N-15` na vlastní zkušební metodice a odmítnutí chráněného obsahu bez licence. Rozsah skutečné licence ověří `15002` a `15001` po převzetí před prvním importem placených textů.
5. **Smlouvy:** šablony balíčku `S1` jsou ukázkové vzory generátoru bez odkazů na předpisy. `Blok 13` do nich jen převádí právní minimum potvrzené advokátem po převzetí systému; každé nové nebo změněné znění smlouvy a směrnice sestaví `15001` z báze a před prvním použitím je posoudí advokát (výstupy `15001` nikdy neposuzuje `15001` sám).

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

V režimu TEST instalační ai v bloku 0 převezme tento registr. U každého bodu provede zkoušku v uvedeném bloku a zapíše výsledek. Když zkouška vyžaduje skutečnou identitu, smlouvu nebo živou protistranu, připraví testovací variantu a zaznamená, co správce ověří po převzetí. Uvedené role odpovídají za produkční rozhodnutí.

| ID | Bod | Kde se používá | Kdo rozhodne nebo ověří | Blok uzavření | Vlastník do vzniku agentů |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `N-10` | Funkce, které návrh připisuje nástrojům z `V-22`, nejsou jejich veřejnými popisy potvrzeny (provoz nástroje `Nod` bez dalšího kontejnerového běhového prostředí a s vypnutou telemetrií; doménová pravidla v `aigiscode`; souhrnná stopka rozpočtu se třemi prahy napříč 20 `ai`; izolace oddělených klonů `wt-worker` / `wt-judge`). Jde o vlastní nadstavbu návrhu, která musí vzniknout vlastním vývojem. | `software/07`, `software/10` | `17001 programator` před nasazením | `Blok 7` (položka `DoD`; část pro `software/10` před nasazením v `Bloku 10`) | Instalační koordinátor + `1001`, po založení agentů `17001` |
| `N-15` | Rozsah, v jakém licence placeného přístupu k normám dovoluje ukládat výtahy do `Vault` a zpracovávat je jazykovým modelem | kapitola 3, karta `15002` | `15002 normovac` + `15001 pravni-specialista` | `Blok 8` ověří technické omezení v TEST. Skutečnou licenci posoudit po převzetí před prvním načtením chráněných textů. | Instalační koordinátor + `1001` |
| `N-16` | **Ověřeno v TEST na Ejpovicích.** OpenBao 2.7.3 vydal pět podílů s prahem tří. Izolovaná obnova z exportu Raftu přečetla shodný záznam. Osobní úschova produkčních klíčů se ověřuje po převzetí. Původní předmět ověření: konfigurace statické pečeti `OpenBao` (`seal "static"`): vyžaduje povinný `current_key_id`, odebrání/odpojení surového pečetního klíče z běžícího kontejneru ihned po odemčení (jinak by kompromitace kontejneru či příkaz `SEAL` umožnily samo-odemčení při restartu) a ujasnění, zda `OpenBao` při `seal "static"` vydává i podíly `Shamir Recovery Keys` (jinak je jedinou cestou obnovy PGP kopie statického klíče v obálce `Break-Glass` a zmínky o podílech se z návodu vypustí). | `software/04`, `README`, kniha `00`, `oddeleni/11`, `oddeleni/17`, karta `17004`, šablona `06b-protokol-break-glass` balíčku `S1` | `17004 klicnik` + `17003 spravce-site` při stavbě `Bloku 4` | `Blok 4` (položka `DoD`) | Instalační koordinátor + `1001` |
| `N-17` | **Ověřeno na Ejpovicích.** VM odemkla klíč přes vTPM, ZFS ověřil také klíč z obnovovací kopie. Doklady jsou v `workspace/dukazy/blok-01/` (`zkouska-zfs-vtpm-20261123T183312Z.txt`, `N-17-overeni-obnovovaci-kopie.txt`). Kontrolu právě nasazené VM zopakuje `nasazeni/test/inventura.py`. Předmět zkoušky zahrnuje šifrování virtuálního datového disku uvnitř VM `polarita-hq`: postup nativního šifrování `OpenZFS` s klíčem zapečetěným ve vTPM 2.0, bezobslužné odemčení datového poolu při startu a obnova ze záložní kopie klíče — ověřit proti oficiální dokumentaci nasazené verze operačního systému a `OpenZFS`. | `software/01`, `README`, kniha `00` | `17003 spravce-site` + `17004 klicnik` při stavbě `Bloku 1` | `Blok 1` (položka `DoD`) | Instalační koordinátor + `1001` |
| `N-18` | `Chatwoot CE`: přesný seznam veřejných cest (widget a webhooky kanálů) a interních cest za VPN + `oauth2-proxy` sestavit z tabulky rout nasazené verze a ověřit e2e testem widgetu i webhooku. | `software/11`, `README`, kniha `00` | `17003 spravce-site` + `17004 klicnik` při stavbě `Bloku 11` | `Blok 11` (položka `DoD`) | Instalační koordinátor + `1001` |
| `N-19` | **Ověřeno v TEST 24. 11. 2026.** Zulip 13.3 přistupuje ke vzdálené PostgreSQL přes TLS. V TEST je mobilní push vypnutý. Zkušební výpadek a obnovu přijaly soukromý kanál `17-it-secops`, místní SMTP a místní testovací příjemce Telegramu. Bezplatný mobilní push výrobce poskytuje běžným firmám s vlastní instalací do deseti uživatelů v organizaci. Registrace a fyzická zkouška mobilního doručení patří k převzetí, pokud si je správce zvolí. [Podmínky výrobce](https://zulip.com/plans/) · [Registrace služby](https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html) | `software/07` | instalační ai v TEST, správce pro produkční push | `Blok 7` | instalační ai |
| `N-20` | `Dangerzone`: balíček a plně offline režim v obrazu bez sítě (`sandbox_airgap`). | `software/04` | `17004 klicnik` + `17003 spravce-site` při stavbě `Bloku 4` | `Blok 4` (položka `DoD`) | Instalační koordinátor + `1001` |
| `N-21` | `Garage`: podpora pravidel životního cyklu (expirace objektů) v nasazené verzi; jinak se `90denní` výmaz provádí plánovanou úlohou. | `software/05` | `17003 spravce-site` při stavbě `Bloku 5` | `Blok 5` (položka `DoD`) | Instalační koordinátor + `1001` |
| `N-22` | Knihovna `libdatovka`: licence a dostupnost jejího Python rozhraní pro `isds-podatelna-bridge`. | `software/08` | `17001 programator` + `15001 pravni-specialista` při stavbě `Bloku 8` | `Blok 8` (položka `DoD`) | Instalační koordinátor + `1001` |
| `N-23` | Podmínky strojového přístupu k rejstříku `CEE`. | `software/11` | `17001 programator` + `15001 pravni-specialista` při stavbě `Bloku 11` | `Blok 11` (položka `DoD`) | Instalační koordinátor + `1001` |
| `N-24` | Plně offline běh všech dílčích modelů `WhisperX` / `pyannote` v zóně bez sítě. | `software/11` | `17001 programator` + `17004 klicnik` při stavbě `Bloku 11` | `Blok 11` (položka `DoD`) | Instalační koordinátor + `1001` |
| `N-25` | **Databáze ověřena v TEST 24. 11. 2026.** Paperclip 2026.1117.0 drží při migracích relační zámek PostgreSQL přes více transakcí. Aplikace proto používá přímé spojení. PostgreSQL potvrdila TLS 1.3 ze síťové adresy instance Paperclipu. Zbývá ověřit přihlášení správce přes Keycloak u Paperclipu. | `software/07` | `17001 programator` + `17003 spravce-site` při stavbě `Bloku 7` | `Blok 7` (položka `DoD`) | Instalační koordinátor + `1001` |
| `N-26` | `Headscale`: registrace uzlu bez vypršení pro nouzový vstup do VPN nezávislý na SSO. | `software/03` | `17003 spravce-site` při stavbě `Bloku 3` | `Blok 3` (položka `DoD`) | Instalační koordinátor + `1001` |
| `N-27` | `PostgreSQL` ve vzoru izolace tenantů: textový tvar hodnoty `search_path` v katalogu funkcí, dostupnost limitu délky celé transakce chování času příkazu při ověřování expirace tokenu relace a chování nasazeného pooleru spojení při vracení spojení (zbytkový kontext relace). | `balicky/S7-polarita-elektro-cloud/rls-vzor.sql` | `17001 programator` + `17004 klicnik` při stavbě `Bloku 19` | `Blok 19` (položka `DoD`) | `1001` |
| `N-28` | `PostgreSQL` ve schématech půjčovny: složený cizí klíč tabulky na sebe sama, vylučovací omezení rezervací (rozšíření `btree_gist`) a atomické operace nad dvojicí stavů. | `balicky/S4-dilensky-terminal-a-pujcovna/schemata/pujcovna.yaml` | `17001 programator` při stavbě `Bloku 16` | `Blok 16` (položka `DoD`) | `1001` |
| `R-01` | Ceny, hodinové sazby, přirážky, minimální marže, stupně provize, sazby DPH (`21 %` / `12 %`) a sezónní koeficienty v [`cenik.json`](./balicky/S3-konfigurator-a-tarify/cenik.json); veřejný konfigurátor čte výhradně výřez `public_price_list` (bez interních sazeb, marží a provizí). | balíček `S3` | **Rozhodnuto 15. 11. 2026:** jednatel `1001` schválil znění návrhu beze změn; porovnání s trhem a zápis do `Decisions` proběhne při založení firmy (`Blok 15`). | `Blok 15` | `1001` |
| `R-02` | Ceník a kauce půjčovny měřidel | [`balicky/S4-dilensky-terminal-a-pujcovna/README.md`](./balicky/S4-dilensky-terminal-a-pujcovna/README.md) | jednatel `1001` | `Blok 16` | `1001` |
| `R-03` | Poskytovatel a úrovně elektronického podpisu; parametry eskalace hlasové recepční | [`balicky/S5-podpis-a-hlasova-recepcni/README.md`](./balicky/S5-podpis-a-hlasova-recepcni/README.md) | jednatel `1001` | `Blok 17` | `1001` |
| `R-04` | Kritéria a prahy brány `Go / No-Go` (návrhové prahy počtu spravovaných objektů a vydaných revizí); ceny a limity tarifů SaaS | [`balicky/S7-polarita-elektro-cloud/README.md`](./balicky/S7-polarita-elektro-cloud/README.md) | jednatel `1001` | `Blok 19` | `1001` |
| `R-05` | **Ověřeno v TEST 24. 11. 2026.** Osm soukromých kanálů odpovídá soupisu `zulip_channels` v `nastroje/kanon.json`. Všech 20 pracovních botů přijalo zprávu a odpovědělo ve svém útvaru. | `README`, `software/07` | instalační ai ověří názvy při nasazení | `Blok 7` | správce po převzetí |

Právní a normové otázky (například platnost smluvních ujednání, režim pokut, harmonizace norem, počítání lhůt) se v tomto registru nevedou: vznikají a řeší se až nad bází na běžícím systému a rozhoduje o nich advokát nebo odborně způsobilá osoba.

## 9. Externí služby a proprietární klienti

Návrh staví na open-source jádru provozovaném na vlastním serveru (`0 Kč` za licence serverového softwaru). Tvrzení „vše open-source“ pro něj neplatí bez výhrady: následující externí služby a proprietární klienti jsou vědomou součástí návrhu, jejich podmínky se ověřují proti oficiální dokumentaci a smluvním podmínkám při stavbě uvedeného bloku a každá změna seznamu se zapisuje sem.

| Služba nebo klient | Druh | K čemu slouží | Blok |
| :--- | :--- | :--- | :--- |
| API a CLI jazykových modelů (alespoň dvě rodiny) | placená externí služba + proprietární klient | běh `ai` agentů, stavitel `Worker` a oponent `Judge` | `Blok 1`, `Blok 7` |
| Klienti `Tailscale` (k vlastnímu serveru `Headscale`) | klient třetí strany | připojení stanic a telefonů do VPN | `Blok 1`, `Blok 3` |
| `Cloudflare` (DNS a ochranná vrstva před veřejným webem) | externí služba | správa zón, ACME DNS-01 | `Blok 3`, `Blok 12` |
| `Telegram` a externí SMTP relay | externí služby | nouzové alerty nezávislé na serveru | `Blok 6` |
| Kvalifikovaný poskytovatel certifikátů a časových razítek (`TSA`) | placená externí služba | osobní `QES`, organizační pečeť, razítka | `Blok 0`, `Blok 4` |
| ISDS (`czebox.cz`, produkční schránka) | služba státu | Podatelna | `Blok 8`, `Blok 12` |
| Bankovní API a účetní API `ORG-UOL` | externí služby (jen čtení) | párování plateb a účetnictví | `Blok 11` |
| `Mapy.cz` API | placená externí služba | trasy a matice výjezdů | `Blok 8` |
| Přístup k normám ČSN Online a licencovaná rozpočtová data | licencovaný obsah | normová báze, rozpočty | `Blok 8`, `Blok 10` |
| `Ecomail`, reklamní platformy | externí služby | e-mailing a placená akvizice (samostatná karta / limit) | `Blok 9`, `Blok 12` |
| `Balíkobot`, platební brána e-shopu | externí služby | expedice a platby | `Blok 9` |
| `SIP Trunk`, `WhatsApp Business API`, SMS brána | externí služby | hlas a zprávy | `Blok 11` |
| Proprietární mobilní a desktopové klienty a obchody s aplikacemi (včetně případné služby mobilních push oznámení `Zulipu`, bod `N-19`) | klienti a služby třetích stran | přístup lidí ke službám | `Blok 1`, `Blok 7` |
