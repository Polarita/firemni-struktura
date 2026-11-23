# 01 — Operační systémy a úložiště (Server, pracovní stanice a mobilní zařízení) · Verze 3.0

Tento dokument definuje výchozí operační systémy pro realizaci čisté hybridní `ai`-first společnosti **Polarita s.r.o.** (pobočka `101` Praha — Centrála i budoucí pobočky `102`–`999`) — postavené na prověřených open-source stavebních kamenech, vlastních modulech oddělení `17` a plné multiplatformní svobodě koncových zařízení.

---

## 1. Seznam vybraného softwaru

| Vrstva / Zařízení | Vybraný software | Kanál / Edice | Role a použití v Polarita s.r.o. (Verze 3.0) | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Centrální server (`polarita-hq`) a pobočkové servery (`101+`)** | **Ubuntu Server** | `latest LTS` *(aktuální dlouhodobě podporovaná verze)* | Jednotný hostitelský operační systém na holém železe (`x86_64`) i případných cloudových uzlech; nese strom `/srv/polarita/` a virtualizační vrstvu `Incus (latest)`. | `17003` `spravce-site` *(kontrola `17004` `klicnik`)* |
| **Souborový systém a disková vrstva serveru** | **OpenZFS** *(fyzický server, zrcadlený `mirror`)* / **ext4 nad `LVM thin` či blokovými snapshoty hypervizoru** *(náhradní varianta na pronajatém virtuálním stroji)* | `latest` *(součást jádra a repozitářů Ubuntu LTS)* | Zrcadlení disků (mirror), kontrolní součty bloků proti tichému poškození archivu a okamžité atomické snapshoty před každou aktualizací (u `ext4` na pronajatém virtuálním stroji povinně na blokové vrstvě `LVM thin` / hypervizoru). | `17003` `spravce-site` |
| **Pracovní stanice (jednatel `1001`, kancelář, spolupracovníci)** | **Windows**, **Linux Desktop** (např. Ubuntu LTS), **Apple macOS** | `latest Pro` / `latest LTS` / `latest` | Plně rovnocenné klientské systémy pro schvalování v `Decisions`, týmovou komunikaci **`Zulip (latest)`**, softphone **`WebRTC` / `Linphone (latest)`**, poštu **`Mozilla Thunderbird (latest)`** (`IMAP IDLE / SMTP / ManageSieve`; přes `Headscale VPN` s heslem aplikace — `JMAP` klient zatím nepodporuje), **výhradní desktopový lokální kvalifikovaný podpis `QES` v `JSignPdf`** přes kontaktní USB čtečku čipu `QSCD`, editor schémat `QElectroTech`, přístup do paměti `Vault`, správu e-shopu, Akademie, účetnictví i VPN. | Multiplatformní podpora *(ověřuje `17002` `webmaster` a `17004` `klicnik`)* |
| **Mobilní telefony a tablety (terén `1002+`, sklad, jednatel, klienti)** | **Android**, **Apple iOS / iPadOS** | `latest` *(s aktivními bezpečnostními záplatami)* | **360° Karta spisu s 1-klik tlačítky `„Pracuj“` (`N2`) a `WebRTC` softphonem**, nativní klienti **`Linphone (latest)`** a **`Zulip (latest)`**, mobilní Zadávací listy práce, večerní hlasové diktování **Elektronického stavebního deníku** a víceprací (`WhisperX`), focení zakrytých prací a dodacích listů, kamerová čtečka QR štítků měřidel/vozidel/`VAN-*`/sběrných boxů `SCRAP-CU`/rozváděčů, klíč **YubiKey** přes `USB-C / NFC` (a u mobilního čtení čipu `eObčanky` spárovaná **Bluetooth čtečka čipových karet**, nikdy NFC telefonu!). | Multiplatformní podpora *(ověřuje `17002` `webmaster` a `17004` `klicnik`)* |

---

## 2. Architektonická pravidla a zdůvodnění výběru

1. **Jednotný serverový standard (`Ubuntu Server — latest LTS`):**
   * Sjednocuje centrální server `polarita-hq` s budoucími pobočkovými servery (`102+`) v infrastruktuře.
   * Poskytuje dlouhodobou bezpečnostní podporu, přímý přístup k hardwarovému modulu TPM pro trezor tajemství a nativní podporu souborového systému `OpenZFS` i jaderného firewallu `nftables`.
   * Server se instaluje vždy v čisté minimální serverové variantě (**bez grafického desktopového prostředí**).
2. **Kanonický adresářový strom `/srv/polarita/` (`0` osobních údajů ve `Vaultu`) a parametry `OpenZFS` (`zfs_arc_max`, `recordsize=8k`):**
   * Veškeré konfigurace infrastruktury (`infra/` vč. `openbao/`), aplikace (`apps/`), databázová a archivní úložiště (`data/` vč. oddělených ZFS datasetů `data/incus`, `data/postgres` s **`recordsize=8k`**, `data/garage`, `data/gitea`, `data/pgbackrest`, `data/legal-archive`, `data/vaultwarden`, předávacího `data/airgap-spool`, modelového `data/airgap-models` a adresáře signatur `ClamAV` `data/clamav-db`), znalostní paměť (`vault/` — výhradně neosobní metodiky, SOP a prázdné šablony, **`0` PII**!), pracovní stoly oddělení `11`–`18` včetně karantény a izolovaných vývojových stromů `wt-worker / wt-judge` (`workspace/`) a lokální zálohy (`backups/`) žijí výhradně pod `/srv/polarita/` s jasnými vlastníky a oprávněními. Na ZFS hostiteli nastav strop paměti cache **`zfs_arc_max`** (např. `6–8 GB` v režimu `MVP 64 GB RAM` tak, aby hostitel + `ARC` nepřesáhly `12 GB`, resp. `16–24 GB` v `Plném režimu 128 GB RAM`), aby zůstala bezpečná rezerva pro `Incus` kontejnery. Datový pool je nativně šifrovaný (`OpenZFS`), klíč je zapečetěn v čipu `TPM 2.0` a odemyká se při startu bez obsluhy; záložní kopie klíče (tištěná + PGP) leží v obálce `Break-Glass`; operační systém je na samostatném zrcadleném oddílu obou disků včetně obou `ESP`. Přesný postup se ověří při stavbě (otevřený bod `N-17` registru [`06`](../06-REGISTR-OVERENI-PRAVA-A-NOREM.md)).
3. **Hardwarové profily (`MVP 64 GB` vs. `Plný 128 GB + GPU`) a zákaz platformního uzamčení na pracovních stanicích:**
   * **`MVP` profil (`16 CPU / 64 GB ECC RAM`):** pokrývá celé jádro `Bloků 1–12` bez dedikované Windows VM, přičemž lokální přepis **`WhisperX`** v `sandbox_airgap` běží jen dávkově (*batch*) v noci na CPU (přepis je k dispozici až následující ráno). **`Plný produkční profil (`16+ CPU / 128 GB ECC RAM + dedikovaná GPU`):**** umožňuje plynulý běh konverzačního/rychlého přepisu **`WhisperX`** na GPU bezprostředně po hovoru, rezervaci RAM pro **`PostgreSQL + ZFS ARC + Zulip + Chatwoot + Moodle`** i případnou izolovanou Windows VM (KVM VM s `Dangerzone` běží v obou profilech).
   * Žádný klíčový firemní proces nesmí vyžadovat, aby jednatel (`1001`) nebo spolupracovník seděl u konkrétního operačního systému.
   * Všechna firemní rozhraní musí být plně ovladatelná z moderního webového prohlížeče a multiplatformních nástrojů (VPN klient, SSH, hardwarový klíč YubiKey).
   * Pokud některý oborový elektrotechnický či rozpočtový program existuje pouze pro Windows, zpřístupní se v Plném profilu přes izolovaný virtuální stroj na serveru (vnořený `/dev/kvm`) tak, aby šel ovládat i z macOS a Linuxu.
4. **Rovnocenná podpora `Android` a `Apple iOS / iPadOS` v terénu:**
   * Terénní rozhraní pro montéry, skladníky, brigádníky a partnery (`1002+`) i čtení QR štítků Digitální knihy objektu se řeší přes responzivní webové rozhraní (PWA) využívající standardní fotoaparát telefonu a otevřené webové standardy funkční na Androidu i Apple zařízeních.

### Co se na server záměrně NEINSTALUJE
* Neinstaluje se samostatný hypervizor přepisující hostitelský systém (např. Proxmox/Debian) — plnou virtualizaci zajišťuje přímo nad `Ubuntu Server (latest LTS)` nástroj `Incus (latest)` (viz Blok `02`).
* Neinstaluje se `Docker` přímo na hostitelský operační systém.
* Neinstalují se neověřené repozitáře třetích stran bez kryptografického ověření podpisového klíče.

---

## 3. Pokyny k instalaci a konfiguraci pro `ai` (Prompty)

> **Pravidlo bezpečného postupu (`Dual-Control`):** `ai` agent nikdy sám nemaže disky ani nemění produkční síť bez předchozího Read-Only průzkumu a schválení plánu vlastníkem (`1001`) ve frontě `Decisions`. Do spuštění fronty `Decisions` (`Prompt 1` `Bloku 7`) se „schválením v `Decisions`“ v `Blocích 1–6` a v `Promptu 1` `Bloku 7` rozumí výslovné písemné schválení plánu jednatelem `1001` přímo v relaci (do vzniku datasetu `workspace` v `Promptu 2` `Bloku 1` písemně mimo server, potom zapsané do `/srv/polarita/workspace/`), od `Promptu 2` `Bloku 7` převedené do fronty `Decisions`. Schválení předchází každému měnícímu kroku každého promptu (ne jen `Promptu 1`): každý `Prompt` začíná čtecím průzkumem a plánem, pak se zastaví pro schválení `1001`. Do konce `Bloku 6` (a v `Bloku 7` do založení agentů) vykonávají prompty adresované `17003 spravce-site`, `17004 klicnik` a `17001 programator` subagenti Instalačního koordinátora (infrastrukturní / vývojový subagent); od založení agentů v `Bloku 7` je přebírají jmenovaní agenti.

> **Cílový stroj:** čistý **fyzický server** (`MVP: 16 jader / 64 GB ECC RAM` bez Windows VM s CPU batch `WhisperX`; `Plný provoz: 16+ jader / 128 GB ECC RAM + dedikovaná GPU`), dva disky NVMe/SSD, čip `TPM 2.0`, `UEFI Secure Boot` a hardwarová virtualizace (`/dev/kvm`). Na hostiteli běží pouze operační systém, `OpenZFS` a `Incus`; **celá firma běží ve virtualizaci uvnitř `Incus`** (`0× Docker`, žádná firemní aplikace přímo na hostiteli). Server nesmí obsahovat data ani služby z žádného dřívějšího provozu. Úplné požadavky a náhradní variantu na pronajatém virtuálním stroji uvádí kap. 1 výchozího [README.md](../README.md).

### Prompt 1 — Průzkum železa a návrh rozložení úložiště před instalací (`pro 17003 spravce-site`)

```text
Jsi správce serveru (17003 spravce-site; do vzniku agentů infrastrukturní subagent Instalačního koordinátora). Připravujeme čistý server polarita-hq pro operační systém Ubuntu Server (latest LTS). Pořadí Bloku 1: průzkum železa a návrh rozložení -> schválení 1001 -> instalace OS a pole (Prompt 2).
Proveď nejprve výhradně čtecí (Read-Only) kontrolu cílového stroje a připrav realizační plán ke schválení do Decisions:

1. Z instalačního / živého prostředí (bez zápisu na disky) ověř připravené instalační médium (Ubuntu Server latest LTS), architekturu CPU, přítomnost hardwarové virtualizace (VT-x / AMD-V, /dev/kvm), velikost RAM, rozložení disků (NVMe/SSD, stav ZFS/ext4), stav UEFI a přítomnost čipu TPM 2.0. Příkazem systemd-detect-virt potvrď, že jde o fyzický server (výsledek none); na náhradní variantě (pronajatý virtuální stroj) ověř virtuální TPM a vnořenou virtualizaci. Ověř, že na stroji nejsou žádná data ani služby z dřívějšího provozu.
2. Zkontroluj, že na stroji neběží grafické prostředí ani nechtěné síťové služby naslouchající do veřejného internetu.
3. Navrhni přesné rozložení úložiště (operační systém na samostatném zrcadleném oddílu obou disků včetně obou ESP; nativně šifrovaný datový pool OpenZFS mirror na dvou discích fyzického serveru s klíčem zapečetěným v TPM 2.0 a bezobslužným odemčením při startu, záložní kopií klíče — tištěnou + PGP — v obálce Break-Glass a postupem ověřeným proti oficiální dokumentaci podle otevřeného bodu N-17; s kompresí lz4, atime=off, limitem zfs_arc_max dle 64/128 GB RAM a oddělenými datasety pro /srv/polarita/, přičemž data/postgres má recordsize=8k a vlastní datasety mají data/incus, data/garage, data/gitea, data/pgbackrest, data/legal-archive, data/vaultwarden, data/airgap-spool, data/airgap-models a adresář signatur ClamAV data/clamav-db; na náhradní variantě pronajatého virtuálního stroje pool OpenZFS nad datovým diskem nebo ext4 nad LVM thin s blokovými snapshoty hypervizoru) s možností pořídit okamžitý atomický snapshot před každou aktualizací; v návrhu uveď i způsob návratu systémového oddílu po nepovedené aktualizaci.
4. Ověř profil hardware: MVP (64 GB RAM — batch CPU WhisperX, bez Windows VM; u VPS bez vnořeného /dev/kvm se Dangerzone v sandbox_airgap nahrazuje bez-síťovou pixelovou rekonstrukcí PDF přes Poppler + QPDF) vs. Plný provoz (128 GB ECC RAM + dedikovaná GPU).
5. Připrav příkazy pro vytvoření čistého kanonického stromu /srv/polarita/{infra,apps,data,vault,workspace,backups} se správnými oprávněními nejmenších privilegií (do /srv/polarita/vault/ se nikdy neukládají osobní údaje PII).
6. Nikde v dokumentaci neuváděj pevně zadrátovaná historická čísla verzí, pracuj s kanálem latest LTS / supported stable dle oficiální matice kompatibility aplikací a exaktní nasazené verze uzamykej v lockfilech v /srv/polarita/infra/ (po Bloku 5 v Gitea / OpenTofu).
7. Nech návrh zkontrolovat u 17004 klicnik a předlož jej ke schválení vlastníkovi (1001) (do spuštění fronty Decisions v Bloku 7 formou výslovného písemného schválení v relaci). Nic na disku zatím neměň.
```

### Prompt 2 — Instalace OS a šifrovaného pole, základní inicializace a zabezpečení po schválení (`pro 17003 spravce-site` + `17004 klicnik`)

```text
Plán instalace a inicializace serveru polarita-hq na Ubuntu Server (latest LTS) z Promptu 1 byl písemně schválen jednatelem 1001. Nejprve čtecí kontrolou ověř skutečný stav stroje proti schválenému plánu, sestav aktualizovaný plán měnících kroků 1–5 (se jmenovitě uvedenou každou odchylkou) a předlož jej 1001; pak se ZASTAV, dokud 1001 aktualizovaný plán výslovně písemně neschválí — vždy, ne jen při odchylce. Teprve potom nainstaluj operační systém a datové pole podle schváleného aktualizovaného plánu a proveď inicializaci a základní hardening:

1. Nainstaluj Ubuntu Server (latest LTS) v minimální serverové variantě na samostatný zrcadlený oddíl obou disků (včetně obou ESP), nastav časové pásmo Europe/Prague, ověř synchronizaci času přes NTP (chrony / systemd-timesyncd) a nastav kanonický hostname malými písmeny dle RFC 1178 (polarita-hq).
2. Aktualizuj systémové balíčky Ubuntu Server (latest LTS) z oficiálních repozitářů a zapni automatické stahování kritických bezpečnostních záplat s řízeným oknem pro restart mimo špičku.
3. Vytvoř adresářovou strukturu /srv/polarita/ (infra vč. openbao, apps, data, vault jako prázdný dataset — Git repozitář v něm vznikne v Bloku 5 a služba paměti v Bloku 8, do té doby se do něj nic nezapisuje —, workspace včetně podsložek oddělení 11–18, dukazy/blok-01 až dukazy/blok-07 pro důkazy a přejímací protokoly Bloků 1–7, karantena, isds-podatelna a ai-finops/eval-suite, backups) s přísnými přístupovými právy (žádné globálně zapisovatelné složky 0777); vytvoř a ověř nativně šifrovaný datový pool OpenZFS mirror (klíč zapečetěný v TPM 2.0 s bezobslužným odemčením při startu; záložní kopie klíče tištěná + PGP do obálky Break-Glass; přesný postup podle N-17; zpool status = ONLINE na obou discích, zfs_arc_max nastaven, komprese lz4, atime=off, oddělené datasety data/incus (prázdný, vyhrazený výhradně Incusu), data/postgres (s recordsize=8k), data/garage, data/gitea, data/pgbackrest, data/legal-archive, data/vaultwarden, data/airgap-spool, data/airgap-models, data/clamav-db, vault, workspace a backups), zapni pravidelné kontroly SMART / zpool scrub a auditní logování auditd.
4. Sjednoť konfiguraci OpenSSH serveru (/etc/ssh/sshd_config.d/00-unified-hardening.conf): zakaž přihlašování heslem (PasswordAuthentication no, KbdInteractiveAuthentication no), zakaž přímé přihlášení uživatele root (PermitRootLogin no) a povol výhradně ověřené Ed25519 klíče. Před restartem sshd ověř syntaxi přes sshd -t, abys neztratil spojení!
5. Vytvoř úvodní čistý snapshot datových datasetů (stav po čisté instalaci) a připrav schválený způsob návratu systémového oddílu; vyzkoušej bezobslužný restart (pool se odemkne bez obsluhy) a obnovu přístupu k poolu ze záložní kopie klíče z obálky Break-Glass.
6. Proveď kontrolní Read-Only ověření (systemctl --failed, ss -tulpn, oprávnění /srv/polarita/, stav SSH a NTP), ulož protokol do /srv/polarita/workspace/dukazy/blok-01/ a předej jej ke kontrole agentovi 17004 klicnik.
```

### Prompt 3 — Kontrolní audit multiplatformní kompatibility klientů a po schválení příprava klientských stanic (`pro 17002 webmaster` a `17004 klicnik`)

```text
Prompt má dvě části: A) čtecí kontrola (kroky 1–3, nic nemění) a plán přípravy klientských stanic; pak se ZASTAV pro písemné schválení 1001; B) po schválení samostatný měnící krok 4 (příprava klientských stanic a uložení matice).
V Bloku 1 ověř jen to, co už existuje (klientská zařízení a jejich nástroje), a sestav matici multiplatformní kompatibility, podle které se každá služba otestuje až v bloku, kde vzniká:

1. Pracovní stanice: Ověř, že na stanicích, které jsou v Bloku 1 k dispozici (Windows latest Pro, Linux Desktop latest LTS, Apple macOS latest), je nainstalován aktuální prohlížeč a klient SSH a že se z nich lze klíčem přihlásit ke správě serveru; u ostatních klientských nástrojů (VPN klient, Zulip, Linphone, Thunderbird, JSignPdf, QElectroTech) jen zjisti, zda jsou nainstalovány, a zapiš je do matice s blokem, ve kterém se funkčně ověří.
2. Mobilní zařízení: Ověř, že telefony a tablety Android (latest) a Apple iOS / iPadOS (latest), které jsou k dispozici, mají aktuální systém se záplatami a aktuální prohlížeč a že je na nich čitelný hardwarový klíč YubiKey přes USB-C / NFC.
3. Matice kompatibility: Sestav matici služba × platforma × blok ověření a plán přípravy stanic (co se na které zařízení doinstaluje) a předlož obojí ke schválení 1001; ZASTAV se. Funkční zkoušky služeb patří do DoD bloků, kde služby vznikají — VPN v Bloku 3, fronta Decisions v Bloku 7, paměť Vault a 360° Karta spisu v Bloku 8, terénní rozhraní (Zadávací listy, fotografie, diktování Stavebního deníku, kamerový skener QR kódů) v Bloku 11; v Bloku 1 se nezkoušejí.
4. Po schválení (měnící krok): Na stanici jednatele 1001 a na terénních mobilních zařízeních doinstaluj schválené klientské nástroje (klient VPN, Zulip, Linphone, Thunderbird, na stanici 1001 JSignPdf s čtečkou čipových karet) — v Bloku 1 se jen instalují, k Headscale se připojí v Bloku 3, k Zulipu v Bloku 7 a k ústředně v Bloku 11 — a schválenou matici s protokolem ulož do /srv/polarita/workspace/dukazy/blok-01/.
5. Pokud by některý zvažovaný software vázal uživatele výhradně na jediný klientský systém bez možnosti webového nebo vzdáleného multiplatformního přístupu, označ jej jako neshodu a navrhni multiplatformní alternativu nebo provoz v izolované serverové VM v Incusu.
```

---

## 4. Ověřitelné podmínky dokončení Bloku 1

- [ ] Na serveru běží čistý **Ubuntu Server (`latest LTS`)** bez grafického prostředí a se `0` selhanými službami (`systemctl --failed`).
- [ ] Čas je synchronizován (`NTP synchronized: yes`), časové pásmo `Europe/Prague`, hostname dle RFC 1178.
- [ ] Existuje strom `/srv/polarita/` se správnými oprávněními (včetně `/srv/polarita/workspace/dukazy/blok-01` až `blok-07`, kam se ukládají důkazy a protokoly `Bloků 1–7`; do `Vaultu` se přenesou až v `Bloku 8`), běží `auditd` a kontroly `SMART / zpool`, čip `TPM 2.0` a `/dev/kvm` jsou dostupné, na hostiteli neběží žádná firemní aplikace a funguje mechanismus atomických snapshotů (na náhradní variantě pronajatého virtuálního stroje `LVM thin` nebo blokové snapshoty hypervizoru).
- [ ] Datový pool `OpenZFS mirror` je nativně šifrovaný (`zpool status = ONLINE` na obou discích, klíč zapečetěný v `TPM 2.0`), operační systém leží na samostatném zrcadleném oddílu obou disků včetně obou `ESP`, bezobslužný restart je vyzkoušen (pool se odemkl bez obsluhy), obnova ze záložní kopie klíče z obálky `Break-Glass` je vyzkoušena a otevřený bod `N-17` je uzavřen zápisem skutečného postupu.
- [ ] Existují datasety `data/airgap-spool`, `data/airgap-models` a adresář signatur `ClamAV` `data/clamav-db`.
- [ ] Přihlášení přes `OpenSSH` funguje výhradně klíčem (`PasswordAuthentication no`, `PermitRootLogin no`).
- [ ] Správa serveru přes `OpenSSH` klíčem je ověřena ze stanice `1001`, na dostupných klientských zařízeních je ověřen aktuální systém, prohlížeč a čitelnost klíče `YubiKey`, schválené klientské nástroje jsou po schválení `1001` nainstalovány (bez připojení ke službám z vyšších bloků) a ve `/srv/polarita/workspace/dukazy/blok-01/` je zapsána matice multiplatformní kompatibility (služba × **Windows**, **Linux**, **Apple macOS**, **Android**, **Apple iOS / iPadOS** × blok ověření); funkční zkoušky `Decisions`, `Vaultu`, 360° Karty spisu a terénních rozhraní nejsou součástí `Bloku 1` — patří do `DoD` bloků, kde tyto služby vznikají.
