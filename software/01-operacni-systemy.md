# 01 — Operační systémy a úložiště (Server, pracovní stanice a mobilní zařízení) · Verze 2.7

Tento dokument definuje výchozí operační systémy pro realizaci čisté hybridní `ai`-first společnosti **Polarita s.r.o.** (pobočka `101` Praha — Centrála i budoucí pobočky `102`–`999`) — postavené na prověřených open-source stavebních kamenech, vlastních modulech oddělení `17` a plné multiplatformní svobodě koncových zařízení.

---

## 1. Seznam vybraného softwaru

| Vrstva / Zařízení | Vybraný software | Kanál / Edice | Role a použití v Polarita s.r.o. (Verze 2.7) | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Centrální server (`polarita-hq`) a pobočkové servery (`101+`)** | **Ubuntu Server** | `latest LTS` *(aktuální dlouhodobě podporovaná verze)* | Jednotný hostitelský operační systém na holém železe (`x86_64`) i případných cloudových uzlech; nese strom `/srv/polarita/` a virtualizační vrstvu `Incus (latest)`. | `17003` `spravce-site` *(kontrola `17004` `klicnik`)* |
| **Souborový systém a disková vrstva serveru** | **OpenZFS** *(fyzický server, zrcadlený `mirror`)* / **ext4 nad `LVM thin` či blokovými snapshoty hypervizoru** *(náhradní varianta na pronajatém virtuálním stroji)* | `latest` *(součást jádra a repozitářů Ubuntu LTS)* | Zrcadlení disků (mirror), kontrolní součty bloků proti tichému poškození archivu a okamžité atomické snapshoty před každou aktualizací (u `ext4` na pronajatém virtuálním stroji povinně na blokové vrstvě `LVM thin` / hypervizoru). | `17003` `spravce-site` |
| **Pracovní stanice (jednatel `1001`, kancelář, spolupracovníci)** | **Windows**, **Linux Desktop** (např. Ubuntu LTS), **Apple macOS** | `latest Pro` / `latest LTS` / `latest` | Plně rovnocenné klientské systémy pro schvalování v `Decisions`, týmovou komunikaci **`Zulip (latest)`**, softphone **`WebRTC` / `Linphone (latest)`**, poštu **`Mozilla Thunderbird (latest)`** (`IMAP IDLE / SMTP / ManageSieve`; `JMAP` klient zatím nepodporuje), kvalifikovaný podpis `QES` v `JSignPdf` přes kontaktní USB čtečku čipu `QSCD`, přístup do paměti `Vault`, správu e-shopu, Akademie, účetnictví i VPN. | Multiplatformní podpora *(ověřuje `17002` `webmaster` a `17004` `klicnik`)* |
| **Mobilní telefony a tablety (terén `1002+`, sklad, jednatel, klienti)** | **Android**, **Apple iOS / iPadOS** | `latest` *(s aktivními bezpečnostními záplatami)* | **360° Karta spisu s 1-klik tlačítky `„Pracuj“` (`N2`) a `WebRTC` softphonem**, nativní klienti **`Linphone (latest)`** a **`Zulip (latest)`**, mobilní Zadávací listy práce, večerní hlasové diktování **Elektronického stavebního deníku** a víceprací (`WhisperX`), focení zakrytých prací a dodacích listů, kamerová čtečka QR štítků měřidel/vozidel/`VAN-*`/sběrných boxů `SCRAP-CU`/rozváděčů, klíč **YubiKey** přes `USB-C / NFC` (a u mobilního čtení čipu `eObčanky` spárovaná **Bluetooth čtečka čipových karet**, nikdy NFC telefonu!). | Multiplatformní podpora *(ověřuje `17002` `webmaster` a `17004` `klicnik`)* |

---

## 2. Architektonická pravidla a zdůvodnění výběru

1. **Jednotný serverový standard (`Ubuntu Server — latest LTS`):**
   * Sjednocuje centrální server `polarita-hq` s budoucími pobočkovými servery (`102+`) v infrastruktuře.
   * Poskytuje dlouhodobou bezpečnostní podporu, přímý přístup k hardwarovému modulu TPM pro trezor tajemství a nativní podporu souborového systému `OpenZFS` i jaderného firewallu `nftables`.
   * Server se instaluje vždy v čisté minimální serverové variantě (**bez grafického desktopového prostředí**).
2. **Kanonický adresářový strom `/srv/polarita/` (`0` osobních údajů ve `Vaultu`):**
   * Veškeré konfigurace infrastruktury (`infra/`), aplikace (`apps/`), databázová a archivní úložiště (`data/`), znalostní paměť (`vault/` — výhradně neosobní metodiky, SOP a prázdné šablony, **`0` PII**!), pracovní stoly oddělení `11`–`18` včetně karantény a izolovaných vývojových stromů `wt-worker / wt-judge` (`workspace/`) a lokální zálohy (`backups/`) žijí výhradně pod `/srv/polarita/` s jasnými vlastníky a oprávněními.
3. **Zákaz platformního uzamčení na pracovních stanicích (`Windows` / `Linux` / `Apple macOS`):**
   * Žádný klíčový firemní proces nesmí vyžadovat, aby jednatel (`1001`) nebo spolupracovník seděl u konkrétního operačního systému.
   * Všechna firemní rozhraní musí být plně ovladatelná z moderního webového prohlížeče a multiplatformních nástrojů (VPN klient, SSH, hardwarový klíč YubiKey).
   * Pokud některý oborový elektrotechnický či rozpočtový program existuje pouze pro Windows, zpřístupní se přes izolovaný virtuální stroj na serveru tak, aby šel ovládat i z macOS a Linuxu.
4. **Rovnocenná podpora `Android` a `Apple iOS / iPadOS` v terénu:**
   * Terénní rozhraní pro montéry, skladníky, brigádníky a partnery (`1002+`) i čtení QR štítků Digitální knihy objektu se řeší přes responzivní webové rozhraní (PWA) využívající standardní fotoaparát telefonu a otevřené webové standardy funkční na Androidu i Apple zařízeních.

### Co se na server záměrně NEINSTALUJE
* Neinstaluje se samostatný hypervizor přepisující hostitelský systém (např. Proxmox/Debian) — plnou virtualizaci zajišťuje přímo nad `Ubuntu Server (latest LTS)` nástroj `Incus (latest)` (viz Blok `02`).
* Neinstaluje se `Docker` přímo na hostitelský operační systém.
* Neinstalují se neověřené repozitáře třetích stran bez kryptografického ověření podpisového klíče.

---

## 3. Pokyny k instalaci a konfiguraci pro `ai` (Prompty)

> **Pravidlo bezpečného postupu (`Dual-Control`):** `ai` agent nikdy sám nemaže disky ani nemění produkční síť bez předchozího Read-Only průzkumu a schválení plánu vlastníkem (`1001`) ve frontě `Decisions`. Do spuštění orchestrátoru `Paperclip` v `Bloku 7` se „schválením v `Decisions`“ v `Blocích 1–6` rozumí výslovné písemné schválení plánu jednatelem `1001` přímo v relaci (do vzniku datasetu `workspace` v `Promptu 2` `Bloku 1` písemně mimo server, potom zapsané do `/srv/polarita/workspace/`), po `Bloku 7` převedené do fronty `Decisions`.

> **Cílový stroj:** čistý **fyzický server** se dvěma disky NVMe/SSD, čipem `TPM 2.0`, `UEFI Secure Boot` a hardwarovou virtualizací (`/dev/kvm`). Na hostiteli běží pouze operační systém, `OpenZFS` a `Incus`; **celá firma běží ve virtualizaci uvnitř `Incus`** (`0× Docker`, žádná firemní aplikace přímo na hostiteli). Server nesmí obsahovat data ani služby z žádného dřívějšího provozu. Úplné požadavky a náhradní variantu na pronajatém virtuálním stroji uvádí kap. 1 výchozího [README.md](../README.md).

### Prompt 1 — Průzkum železa a návrh čisté instalace / inicializace serveru (`pro 17003 spravce-site`)

```text
Jsi správce serveru (17003 spravce-site). Připravujeme čistý server polarita-hq na operačním systému Ubuntu Server (latest LTS).
Proveď nejprve výhradně čtecí (Read-Only) kontrolu cílového stroje a připrav realizační plán ke schválení do Decisions:

1. Ověř přesnou edici OS (Ubuntu Server latest LTS), architekturu CPU, přítomnost hardwarové virtualizace (VT-x / AMD-V, /dev/kvm), velikost RAM, rozložení disků (NVMe/SSD, stav ZFS/ext4), stav UEFI a přítomnost čipu TPM 2.0. Příkazem systemd-detect-virt potvrď, že jde o fyzický server (výsledek none); na náhradní variantě (pronajatý virtuální stroj) ověř virtuální TPM a vnořenou virtualizaci. Ověř, že na stroji nejsou žádná data ani služby z dřívějšího provozu.
2. Zkontroluj, že na stroji neběží grafické prostředí ani nechtěné síťové služby naslouchající do veřejného internetu.
3. Navrhni přesné rozložení úložiště (OpenZFS mirror na dvou discích fyzického serveru s kompresí zstd/lz4 a datasetem pro /srv/polarita/; na náhradní variantě pronajatého virtuálního stroje pool OpenZFS nad datovým diskem nebo ext4 nad LVM thin s blokovými snapshoty hypervizoru) s možností pořídit okamžitý atomický snapshot před každou aktualizací.
4. Připrav příkazy pro vytvoření čistého kanonického stromu /srv/polarita/{infra,apps,data,vault,workspace,backups} se správnými oprávněními nejmenších privilegií (do /srv/polarita/vault/ se nikdy neukládají osobní údaje PII).
5. Nikde v dokumentaci neuváděj pevně zadrátovaná historická čísla verzí, pracuj s kanálem latest LTS / supported stable dle oficiální matice kompatibility aplikací a exaktní nasazené verze uzamykej v lockfilech v /srv/polarita/infra/ (po Bloku 5 v Gitea / OpenTofu).
6. Nech návrh zkontrolovat u 17004 klicnik a předlož jej ke schválení vlastníkovi (1001) (do spuštění fronty Decisions v Bloku 7 formou výslovného písemného schválení v relaci). Nic na disku zatím neměň.
```

### Prompt 2 — Provedení základní inicializace a zabezpečení OS po schválení (`pro 17003 spravce-site` + `17004 klicnik`)

```text
Plán inicializace serveru polarita-hq na Ubuntu Server (latest LTS) byl schválen v Decisions. Proveď inicializaci a základní hardening operačního systému:

1. Nastav časové pásmo Europe/Prague, ověř synchronizaci času přes NTP (chrony / systemd-timesyncd) a nastav kanonický hostname malými písmeny dle RFC 1178 (polarita-hq).
2. Aktualizuj systémové balíčky Ubuntu Server (latest LTS) z oficiálních repozitářů a zapni automatické stahování kritických bezpečnostních záplat s řízeným oknem pro restart mimo špičku.
3. Vytvoř adresářovou strukturu /srv/polarita/ (infra, apps, data, vault včetně 07-IT-a-Architektura pro přejímací protokoly, workspace včetně podsložek oddělení 11–18, karantena, isds-podatelna a ai-finops/eval-suite, backups) s přísnými přístupovými právy (žádné globálně zapisovatelné složky 0777); ověř šifrovaný OpenZFS mirror (zpool status = ONLINE na obou discích, komprese lz4/zstd, atime=off, oddělené datasety data/incus (prázdný, vyhrazený výhradně Incusu), data/postgres, data/legal-archive, vault, workspace a backups), zapni pravidelné kontroly SMART / zpool scrub a auditní logování auditd.
4. Sjednoť konfiguraci OpenSSH serveru (/etc/ssh/sshd_config.d/00-unified-hardening.conf): zakaž přihlašování heslem (PasswordAuthentication no, KbdInteractiveAuthentication no), zakaž přímé přihlášení uživatele root (PermitRootLogin no) a povol výhradně ověřené Ed25519 klíče. Před restartem sshd ověř syntaxi přes sshd -t, abys neztratil spojení!
5. Vytvoř úvodní čistý snapshot souborového systému (stav po čisté instalaci) pro možnost návratu do 3 minut.
6. Proveď kontrolní Read-Only ověření (systemctl --failed, ss -tulpn, oprávnění /srv/polarita/, stav SSH a NTP) a předej protokol ke kontrole agentovi 17004 klicnik.
```

### Prompt 3 — Kontrolní audit multiplatformní kompatibility klientů (`pro 17002 webmaster` a `17004 klicnik`)

```text
Při přípravě a nasazování jakéhokoliv nástroje ve společnosti Polarita s.r.o. proveď povinnou kontrolu multiplatformní přístupnosti pro koncová zařízení:

1. Pracovní stanice: Ověř, že administrace, schvalovací fronta Decisions, sdílená paměť Vault i klientské nástroje fungují bez omezení na operačních systémech Windows (latest Pro), Linux Desktop (latest LTS) i Apple macOS (latest) přes standardní prohlížeč a multiplatformní klienty.
2. Mobilní zařízení: Ověř, že webová a terénní rozhraní (360° Karta spisu s 1-klik tlačítky „Pracuj“, mobilní Zadávací listy, nahrávání fotografií ze stavby, hlasové diktování Stavebního deníku, kamerový skener QR kódů měřidel/vozidel/rozváděčů a přihlašování hardwarovým klíčem YubiKey přes USB-C / NFC) fungují plnohodnotně na systémech Android (latest) i Apple iOS / iPadOS (latest).
3. Pokud by některý zvažovaný software vázal uživatele výhradně na jediný klientský systém bez možnosti webového nebo vzdáleného multiplatformního přístupu, označ jej jako neshodu a navrhni multiplatformní alternativu nebo provoz v izolované serverové VM v Incusu.
```

---

## 4. Ověřitelné podmínky dokončení Bloku 1

- [ ] Na serveru běží čistý **Ubuntu Server (`latest LTS`)** bez grafického prostředí a se `0` selhanými službami (`systemctl --failed`).
- [ ] Čas je synchronizován (`NTP synchronized: yes`), časové pásmo `Europe/Prague`, hostname dle RFC 1178.
- [ ] Existuje strom `/srv/polarita/` se správnými oprávněními, běží `auditd` a kontroly `SMART / zpool`, čip `TPM 2.0` a `/dev/kvm` jsou dostupné, na hostiteli neběží žádná firemní aplikace a funguje mechanismus atomických snapshotů (šifrovaný `OpenZFS mirror` se stavem `zpool status = ONLINE` na obou discích; na náhradní variantě pronajatého virtuálního stroje `LVM thin` nebo blokové snapshoty hypervizoru).
- [ ] Přihlášení přes `OpenSSH` funguje výhradně klíčem (`PasswordAuthentication no`, `PermitRootLogin no`).
- [ ] Žádná komponenta neblokuje práci z klientských stanic **Windows**, **Linux**, **Apple macOS** ani z telefonů **Android** a **Apple iOS / iPadOS**.
