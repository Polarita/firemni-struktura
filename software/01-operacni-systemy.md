# 01 — Operační systémy a úložiště (Server, pracovní stanice a mobilní zařízení) · Verze 3.2.1

Tento dokument definuje výchozí operační systémy pro realizaci čisté hybridní `ai`-first společnosti **Polarita s.r.o.** (pobočka `101` Praha — Centrála i budoucí pobočky `102`–`999`) — postavené na prověřených open-source stavebních kamenech, vlastních modulech oddělení `17` a plné multiplatformní svobodě koncových zařízení.

---

## 1. Seznam vybraného softwaru

| Vrstva / Zařízení | Vybraný software | Kanál / Edice | Role a použití v Polarita s.r.o. (Verze 3.2.1) | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Centrální server (`polarita-hq`) a pobočkové servery (`101+`)** | **Ubuntu Server** | `latest LTS` *(aktuální dlouhodobě podporovaná verze)* | Jednotný hostitelský operační systém uvnitř VM `polarita-hq` v projektu `polarita`; nese strom `/srv/polarita/` a virtualizační vrstvu `Incus (latest)`. | `17003` `spravce-site` *(kontrola `17004` `klicnik`)* |
| **Úložiště VM** | **Ceph** ve vnějším clusteru, systémový disk s Ubuntu a šifrovaný datový pool **OpenZFS** uvnitř VM | podporované stabilní verze | Vnější Incus ukládá virtuální disky do poolu `zrcadlo`. Vnitřní správce pracuje s přiděleným datovým diskem a ověřuje šifrování, snímky a obnovu. | `17003` `spravce-site` |
| **Pracovní stanice (jednatel `1001`, kancelář, spolupracovníci)** | **Windows**, **Linux Desktop** (např. Ubuntu LTS), **Apple macOS** | `latest Pro` / `latest LTS` / `latest` | Plně rovnocenné klientské systémy pro schvalování v `Decisions`, týmovou komunikaci **`Zulip (latest)`**, softphone **`WebRTC` / `Linphone (latest)`**, poštu **`Mozilla Thunderbird (latest)`** (`IMAP IDLE / SMTP / ManageSieve`; přes `Headscale VPN` s heslem aplikace — `JMAP` klient zatím nepodporuje), **výhradní desktopový lokální kvalifikovaný podpis `QES` v `JSignPdf`** přes kontaktní USB čtečku čipu `QSCD`, editor schémat `QElectroTech`, přístup do paměti `Vault`, správu e-shopu, Akademie, účetnictví i VPN. | Multiplatformní podpora *(ověřuje `17002` `webmaster` a `17004` `klicnik`)* |
| **Mobilní telefony a tablety (terén `1002+`, sklad, jednatel, klienti)** | **Android**, **Apple iOS / iPadOS** | `latest` *(s aktivními bezpečnostními záplatami)* | **360° Karta spisu s 1-klik tlačítky `„Pracuj“` (`N2`) a `WebRTC` softphonem**, nativní klienti **`Linphone (latest)`** a **`Zulip (latest)`**, mobilní Zadávací listy práce, večerní hlasové diktování **Elektronického stavebního deníku** a víceprací (`WhisperX`), focení zakrytých prací a dodacích listů, kamerová čtečka QR štítků měřidel/vozidel/`VAN-*`/sběrných boxů `SCRAP-CU`/rozváděčů, klíč **YubiKey** přes `USB-C / NFC` (a u mobilního čtení čipu `eObčanky` spárovaná **Bluetooth čtečka čipových karet**, nikdy NFC telefonu!). | Multiplatformní podpora *(ověřuje `17002` `webmaster` a `17004` `klicnik`)* |

---

## 2. Architektonická pravidla a zdůvodnění výběru

1. **Jednotný serverový standard (`Ubuntu Server — latest LTS`):**
   * Sjednocuje centrální server `polarita-hq` s budoucími pobočkovými servery (`102+`) v infrastruktuře.
   * Poskytuje dlouhodobou bezpečnostní podporu, podporu virtuálního TPM uvnitř VM pro trezor tajemství a nativní podporu souborového systému `OpenZFS` i jaderného firewallu `nftables`.
   * Server se instaluje vždy v čisté minimální serverové variantě (**bez grafického desktopového prostředí**).
2. **Kanonický adresářový strom `/srv/polarita/` (`0` osobních údajů ve `Vaultu`) a parametry `OpenZFS` (`zfs_arc_max`, `recordsize=8k`):**
   * Veškeré konfigurace infrastruktury (`infra/` vč. `openbao/`), aplikace (`apps/`), databázová a archivní úložiště (`data/` vč. oddělených ZFS datasetů `data/incus`, `data/postgres` s **`recordsize=8k`**, `data/garage`, `data/gitea`, `data/pgbackrest`, `data/legal-archive`, `data/vaultwarden`, předávacího `data/airgap-spool`, modelového `data/airgap-models` a adresáře signatur `ClamAV` `data/clamav-db`), znalostní paměť (`vault/` — výhradně neosobní metodiky, SOP a prázdné šablony, **`0` PII**!), pracovní stoly oddělení `11`–`18` včetně karantény a izolovaných vývojových stromů `wt-worker / wt-judge` (`workspace/`) a lokální zálohy (`backups/`) žijí výhradně pod `/srv/polarita/` s jasnými vlastníky a oprávněními. Uvnitř VM nastav strop paměti cache **`zfs_arc_max`** (např. `6–8 GB` v režimu `MVP 64 GB RAM` tak, aby hostitel + `ARC` nepřesáhly `12 GB`, resp. `16–24 GB` v `Plném režimu 128 GB RAM`), aby zůstala bezpečná rezerva pro `Incus` kontejnery. Datový pool je nativně šifrovaný (`OpenZFS`), klíč je zapečetěn pomocí vTPM 2.0 a odemyká se při startu bez obsluhy; záložní kopie klíče (tištěná + PGP) leží v obálce `Break-Glass`; systém a EFI jsou na virtuálním systémovém disku, replikaci jeho bloků zajišťuje Ceph. Přesný postup se ověří při stavbě (otevřený bod `N-17` registru [`06`](../06-REGISTR-OVERENI-PRAVA-A-NOREM.md)).
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

**Zkouška při automatické instalaci.** Zaznamenej přidělené prostředky a ověř obnovitelnost pracovních dat. Klientský test provede prohlížeč přes VPN. Osobní podpisovou výbavu eviduj při převzetí. Níže uvedené kroky s živou protistranou či osobním vybavením jsou součástí produkční aktivace po převzetí.


> V režimu TEST proveď průzkum, ulož plán a automaticky nasaď a ověř změny. Použij testovací data a místní protějšky externích služeb. Skutečné osobní klíče, certifikáty a živé účty zapoj až po uživatelském testu a převzetí správcem.

> **Cílový stroj:** VM `polarita-hq` v projektu `polarita` na uzlu `ejpovice`. Vnější cluster zajišťuje přidělené prostředky a replikaci virtuálních disků v poolu `zrcadlo`. Všechny následující kroky instalace systému, SSH, úložiště a auditních služeb proveď uvnitř této VM. Fyzické SMART a stav Ceph sleduje správce clusteru.

### Prompt 1 — Průzkum VM a návrh rozložení úložiště před instalací (`pro 17003 spravce-site`)

```text
V režimu TEST proveď instalaci samostatně. Kroky vyžadující osobní identitu nebo ostrý účet eviduj pro aktivaci po uživatelském testu a převzetí.
Jsi správce serveru (17003 spravce-site; do vzniku agentů infrastrukturní subagent Instalačního koordinátora). Připravujeme VM polarita-hq pro operační systém Ubuntu Server (latest LTS). Pořadí Bloku 1: průzkum VM a návrh rozložení -> ověření cíle -> příprava OS a datového disku VM (Prompt 2).
Proveď nejprve výhradně čtecí (Read-Only) kontrolu cílového stroje a připrav realizační plán:

1. Ve vnějším Incusu ověř projekt polarita, jméno polarita-hq, uzel ejpovice, limity CPU/RAM a pool zrcadlo. Vstup do VM. Zkontroluj hostname, systemd-detect-virt (kvm), Ubuntu LTS, přidělené virtuální disky a jejich existující obsah. Ověř UEFI, Secure Boot, vTPM 2.0, příznaky vmx/svm a /dev/kvm uvnitř VM. Zapiš chybějící zařízení před návrhem změn.
2. Zkontroluj, že na stroji neběží grafické prostředí ani nechtěné síťové služby naslouchající do veřejného internetu.
3. Navrhni šifrovaný datový pool OpenZFS na vyhrazeném virtuálním disku z poolu zrcadlo. Identifikuj jej uvnitř VM a dolož jeho obsah a odlišení od systémového disku s EFI. Redundanci zajišťuje Ceph. Podle bodu N-17 navrhni bezobslužné odemčení přes vTPM, oddělenou záložní kopii klíče a její zkoušku. Uveď datasety z kap. 2, kompresi lz4, atime=off, recordsize=8k pro PostgreSQL, limit ARC vzhledem k přidělené RAM a konzistentní snímky a návrat systému VM.
4. Ověř kapacitu přidělenou VM: MVP (64 GB RAM — batch CPU WhisperX, bez Windows VM; ve VM bez vnořeného /dev/kvm se Dangerzone v sandbox_airgap nahrazuje bez-síťovou pixelovou rekonstrukcí PDF přes Poppler + QPDF) vs. Plný provoz (128 GB ECC RAM + dedikovaná GPU).
5. Připrav příkazy pro vytvoření čistého kanonického stromu /srv/polarita/{infra,apps,data,vault,workspace,backups} se správnými oprávněními nejmenších privilegií (do /srv/polarita/vault/ se nikdy neukládají osobní údaje PII).
6. Nikde v dokumentaci neuváděj pevně zadrátovaná historická čísla verzí, pracuj s kanálem latest LTS / supported stable dle oficiální matice kompatibility aplikací a exaktní nasazené verze uzamykej v lockfilech v /srv/polarita/infra/ (po Bloku 5 v Gitea / OpenTofu).
7. Ověř plán proti inventuře a ulož jej před změnou disků.
```

### Prompt 2 — Instalace OS a šifrovaného pole, základní inicializace a zabezpečení (`pro 17003 spravce-site` + `17004 klicnik`)

```text
V režimu TEST proveď průzkum, ulož plán a automaticky nasaď a ověř změny. Použij testovací data a místní protějšky externích služeb. Skutečné osobní klíče, certifikáty a živé účty zapoj až po uživatelském testu a převzetí správcem.

1. Ověř nebo podle ověřeného plánu nainstaluj Ubuntu Server latest LTS na systémový disk VM. Nastav hostname polarita-hq, pásmo Europe/Prague a synchronizaci času. Pokud je systém již připraven, použij stávající instalaci.
2. Aktualizuj systémové balíčky Ubuntu Server (latest LTS) z oficiálních repozitářů a zapni automatické stahování kritických bezpečnostních záplat s řízeným oknem pro restart mimo špičku.
3. Vytvoř adresářovou strukturu /srv/polarita/ (infra vč. openbao, apps, data, vault jako prázdný dataset — Git repozitář v něm vznikne v Bloku 5 a služba paměti v Bloku 8, do té doby se do něj nic nezapisuje —, workspace včetně podsložek oddělení 11–18, dukazy/blok-00 až dukazy/blok-07 pro důkazy a přejímací protokoly Bloků 0–7 (do blok-00 ulož protokol splnění vstupů Bloku 0 — vyplněnou kanonickou tabulku vstupů s odkazy na důkazy, bez tajemství a PII), karantena, isds-podatelna a ai-finops/eval-suite, backups) s přísnými přístupovými právy (žádné globálně zapisovatelné složky 0777); vytvoř a ověř nativně šifrovaný datový pool OpenZFS na samostatném virtuálním disku (klíč zapečetěný ve vTPM 2.0 s bezobslužným odemčením při startu; záložní kopie klíče tištěná + PGP do obálky Break-Glass; přesný postup podle N-17; zpool status = ONLINE uvnitř VM, zfs_arc_max nastaven, komprese lz4, atime=off, oddělené datasety data/incus (prázdný, vyhrazený výhradně Incusu), data/postgres (s recordsize=8k), data/garage, data/gitea, data/pgbackrest, data/legal-archive, data/vaultwarden, data/airgap-spool, data/airgap-models, data/clamav-db, vault, workspace a backups), zapni pravidelné kontroly zpool scrub uvnitř VM a auditní logování auditd.
4. Sjednoť konfiguraci OpenSSH serveru (/etc/ssh/sshd_config.d/00-unified-hardening.conf): zakaž přihlašování heslem (PasswordAuthentication no, KbdInteractiveAuthentication no), zakaž přímé přihlášení uživatele root (PermitRootLogin no) a povol výhradně ověřené Ed25519 klíče. Před restartem sshd ověř syntaxi přes sshd -t, abys neztratil spojení!
5. Vytvoř úvodní čistý snapshot datových datasetů (stav po čisté instalaci) a ověř způsob návratu systémového oddílu; vyzkoušej bezobslužný restart (pool se odemkne bez obsluhy) a obnovu přístupu k poolu ze záložní kopie klíče z obálky Break-Glass.
6. Proveď kontrolní Read-Only ověření (systemctl --failed, ss -tulpn, oprávnění /srv/polarita/, stav SSH a NTP), ulož protokol do /srv/polarita/workspace/dukazy/blok-01/ a předej jej ke kontrole agentovi 17004 klicnik.
```

### Prompt 3 — Kontrolní audit multiplatformní kompatibility klientů a příprava klientských stanic (`pro 17002 webmaster` a `17004 klicnik`)

```text
V režimu TEST proveď instalaci samostatně. Kroky vyžadující osobní identitu nebo ostrý účet eviduj pro aktivaci po uživatelském testu a převzetí.
Zjisti podporované klienty a připrav jejich matici. První přihlášení otestuj v běžném prohlížeči.
V Bloku 1 ověř jen to, co už existuje (klientská zařízení a jejich nástroje), a sestav matici multiplatformní kompatibility, podle které se každá služba otestuje až v bloku, kde vzniká:

1. Pracovní stanice: Ověř, že na stanicích, které jsou v Bloku 1 k dispozici (Windows latest Pro, Linux Desktop latest LTS, Apple macOS latest), je nainstalován aktuální prohlížeč a klient SSH a že se z nich lze klíčem přihlásit ke správě serveru; u ostatních klientských nástrojů (VPN klient, Zulip, Linphone, Thunderbird, JSignPdf, QElectroTech) jen zjisti, zda jsou nainstalovány, a zapiš je do matice s blokem, ve kterém se funkčně ověří.
2. Mobilní zařízení: Ověř, že telefony a tablety Android (latest) a Apple iOS / iPadOS (latest), které jsou k dispozici, mají aktuální systém se záplatami a aktuální prohlížeč a že je na nich čitelný hardwarový klíč YubiKey přes USB-C / NFC.
3. Matice kompatibility: Sestav matici služba × platforma × blok ověření a plán přípravy stanic (co se na které zařízení doinstaluje) a ulož výsledek. Funkční zkoušky služeb patří do DoD bloků, kde služby vznikají — VPN v Bloku 3, fronta Decisions v Bloku 7, paměť Vault a 360° Karta spisu v Bloku 8, terénní rozhraní (Zadávací listy, fotografie, diktování Stavebního deníku, kamerový skener QR kódů) v Bloku 11; v Bloku 1 se nezkoušejí.
4. Ověř přístup z dostupných prohlížečů. Osobní podpisové nástroje eviduj jako krok po převzetí. Ulož výsledky.
5. Pokud by některý zvažovaný software vázal uživatele výhradně na jediný klientský systém bez možnosti webového nebo vzdáleného multiplatformního přístupu, označ jej jako neshodu a navrhni multiplatformní alternativu nebo provoz v izolované serverové VM v Incusu.
```

---

## 4. Ověřitelné podmínky dokončení Bloku 1

- [ ] Na serveru běží čistý **Ubuntu Server (`latest LTS`)** bez grafického prostředí a se `0` selhanými službami (`systemctl --failed`).
- [ ] Čas je synchronizován (`NTP synchronized: yes`), časové pásmo `Europe/Prague`, hostname dle RFC 1178.
- [ ] Existuje strom `/srv/polarita/` se správnými oprávněními (včetně `/srv/polarita/workspace/dukazy/blok-00` až `blok-07`, kam se ukládají důkazy a protokoly `Bloků 0–7`; v `blok-00` je uložen protokol splnění vstupů `Bloku 0` bez tajemství a PII; do `Vaultu` se přenesou až v `Bloku 8`), běží `auditd` a kontroly `zpool` uvnitř VM, zařízení vTPM 2.0 a `/dev/kvm` jsou dostupné, na hostiteli neběží žádná firemní aplikace a funguje mechanismus atomických snapshotů.
- [ ] Vnější Incus ukládá virtuální disky VM do poolu `zrcadlo`. Uvnitř VM je systémový disk s EFI a samostatný šifrovaný datový pool OpenZFS. `zpool status` a `zfs get encryption` potvrzují stav a šifrování. Po restartu VM bylo ověřeno odemčení přes vTPM i následná obnova ze záložního klíče. Výsledek uzavírá `N-17` v registru 06.
- [ ] Existují datasety `data/airgap-spool`, `data/airgap-models` a adresář signatur `ClamAV` `data/clamav-db`.
- [ ] Přihlášení přes `OpenSSH` funguje výhradně klíčem (`PasswordAuthentication no`, `PermitRootLogin no`).
- [ ] Správa serveru přes `OpenSSH` klíčem je ověřena ze stanice `1001`, na dostupných klientských zařízeních je ověřen aktuální systém, prohlížeč a čitelnost klíče `YubiKey`, schválené klientské nástroje jsou evidovány podle režimu (bez připojení ke službám z vyšších bloků) a ve `/srv/polarita/workspace/dukazy/blok-01/` je zapsána matice multiplatformní kompatibility (služba × **Windows**, **Linux**, **Apple macOS**, **Android**, **Apple iOS / iPadOS** × blok ověření); funkční zkoušky `Decisions`, `Vaultu`, 360° Karty spisu a terénních rozhraní nejsou součástí `Bloku 1` — patří do `DoD` bloků, kde tyto služby vznikají.
