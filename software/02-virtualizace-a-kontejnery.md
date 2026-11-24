# 02 — Virtualizace, kontejnerizace a izolace zón (Bez Dockeru na hostiteli) · Verze 3.2.2

Tento dokument stanovuje jednotnou virtualizační a kontejnerovou platformu na centrálním serveru `polarita-hq` (`Ubuntu Server — latest LTS`) pro provoz všech aplikací, databází, komunikační ústředny, bez-síťové karantény i testů obnovy společnosti **Polarita s.r.o.** Instalační příkazy, profily, čtyři zóny a OpenTofu v této vrstvě patří do vnitřního Incusu ve VM `polarita-hq`. Vnější Incus poskytuje firemní VM a její disk v poolu `zrcadlo`.

---

## 1. Seznam vybraného softwaru

| Komponenta | Vybraný software | Kanál / Zdroj | Role a použití v Polarita s.r.o. (Verze 3.2.2) | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Jednotný správce virtuálních strojů a kontejnerů** | **Incus** | `latest` *(oficiální podepsaný stabilní repozitář Zabbly)* | Spouští pod jedním nástrojem plné virtuální stroje (`KVM`), lehké systémové kontejnery (`LXC`) i hotové aplikační obrazy (`OCI` přímo z Docker Hubu / GHCR) — zcela bez nutnosti instalovat Docker na hostitele. | `17003` `spravce-site` *(kontrola `17004` `klicnik`)* |
| **Hardwarová virtualizace plných VM** | **QEMU / KVM** *(s UEFI OVMF)* | `latest` *(ovládáno přímo přes `Incus`)* | Hardwarově oddělené virtuální stroje pro bez-síťový sandbox (`sandbox_airgap` — výkresy, přílohy `.zfo`, hlasové zprávy a přílohy z `Chatwoot CE / Stalwart Mail` i 48h převzetí šanonů `N7`), čtvrtletní *Full DR Drill* obnovy záloh a případnou izolovanou Windows VM pro oborový elektro software. | `17003` `spravce-site` |
| **Deklarativní správa infrastruktury (IaC)** | **OpenTofu** + provider **`lxc/incus`** | `latest` *(oficiální podepsaný balíček a uzamčený provider)* | Veškeré sítě, profily, úložiště, kontejnery (vč. `Asterisk`, `WhisperX`, `Zulip`, `Stalwart Mail`, `Chatwoot CE`) i virtuální stroje vytváří a spravuje `ai` agent deklarativně v souborech `.tf` (auditovatelný plán před každou změnou, kontrola odchylek `drift`). | `17003` `spravce-site` *(revize `17004` `klicnik`)* |

---

## 2. Architektonická pravidla a proč nepoužíváme Docker na hostiteli

1. **Jeden nástroj místo tří (`Incus latest` pokrývá všechny tři režimy běhu):**
   * **Režim A — Systémové kontejnery (`LXC`):** Lehké izolované instance `Ubuntu (latest LTS)` s minimální režií paměti RAM pro databáze, reverzní proxy, weby, e-shop, Akademii, softwarovou ústřednu **`Asterisk`**, přepisový worker **`WhisperX`**, týmový **`Zulip`**, poštovní **`Stalwart Mail`**, omnichannel **`Chatwoot CE`** a interní služby. Spravují se čitelně jako běžný Linux a zálohují jedním příkazem.
   * **Režim B — Nativní aplikační kontejnery (`OCI` bez Dockeru):** `Incus (latest)` umí přes protokol `oci` přímo stahovat a spouštět hotové aplikační obrazy z veřejných registrů (`docker.io`, `ghcr.io`). Není tak potřeba instalovat démon `Docker` ani `containerd` na hlavní server.
   * **Režim C — Plné virtuální stroje (`KVM VM`):** Vlastní jádro a plná hardwarová izolace přes `/dev/kvm`. Používá se všude tam, kde je nutná nejvyšší bezpečnostní zeď (`Dangerzone` s Podmanem nad cizími přílohami — na cloudovém VPS bez vnořeného `/dev/kvm` přepíná automaticky na bez-síťový `LXC` s pixelovou rekonstrukcí **`Poppler + QPDF`**), čistá VM pro čtvrtletní *Full Bare-Metal / VM DR Drill* (týdenní nedělní test obnovy v `03:00` běží v odpojeném kontejneru) nebo v Plném 128 GB profilu pro izolovanou Windows VM přístupnou ze stanic Windows, Linux i Apple macOS.
2. **Čistý firewall, jednoznačné 4 síťové zóny bez kolizí a pevné limity RAM / CPU instancí:**
   * Vynecháním Dockeru na hostitelském serveru odpadá přepisování firewallu démonem Dockeru. Všechny 4 síťové zóny firmy spravuje jednotně `Incus (latest)` nad jaderným `nftables`:
     1. `dmz_edge` — výhradně veřejná hrana (`Caddy` na `80/443`, `Headscale` `443` + `3478/udp` STUN a izolovaný příchozí MX relay `Stalwart Mail` na `25/tcp`; **žádné aplikační storefronty ani Node.js SSR, a `0` veřejných příchozích SIP portů**),
     2. `app_internal` — kompletní aplikační, storefrontová a komunikační vrstva webů (`polarita.cz`, storefront `polarita.eu`), e-shopu `MedusaJS`, Akademie `Moodle`, `portal-spolupracovniku`, `Keycloak`, `SilverBullet`, `Gitea`, ústředny `Asterisk`, `Zulip`, `Chatwoot CE`, `Stalwart Mail` jádra, `comm-gateway` a `ai` orchestrátoru `Paperclip`,
     3. `data_vault` — izolovaná databázová a trezorová komora **bez přístupu do internetu** (`PostgreSQL + PgBouncer`, `Valkey`, `Garage`, `OpenBao`, `Vaultwarden`),
     4. `sandbox_airgap` — zcela odpojené prostředí **bez síťového rozhraní (`eth0` přepsáno na `type = "none"`, tj. `eth0 none` v profilu Incus)** pro bezpečné čtení nedůvěryhodných cizích souborů a hlasových zpráv jediným tokem karanténa `/srv/polarita/workspace/karantena` → předávací spool `/srv/polarita/data/airgap-spool` → zpracování → výstup spoolu (`WhisperX` s `HF_HUB_OFFLINE=1`, `Silero VAD + librosa`, `ClamAV + Dangerzone` / `Poppler + QPDF`).
   * **Rozpočet RAM a CPU limitů v OpenTofu (`MVP 64 GB` vs. `Plný 128 GB + GPU`):** V profilu `MVP` je součet limitů instancí nejvýše `52 GB` a hostitel (`OS + OpenZFS zfs_arc_max + Incus`) nejvýše `12 GB` — závazné výchozí hodnoty po instancích uvádí tabulka limitů níže (`dmz_edge` `2 GB`, `data_vault` `14 GB`, `app_internal` `27,5 GB`, `sandbox_airgap` `8 GB`); součet `limits.cpu` se drží na počtu jader hostitele. V `MVP` neběží Windows VM, GPU ani plný `WhisperX` (jen dávkově v noci na CPU). V Plném 128 GB profilu lze limity úměrně zvýšit (hostitel a `ARC` `~20–24 GB`, dedikovaná GPU pro `WhisperX`, volitelná VM `32+ GB`). Každou instanci uzamyká `limits.memory`, `limits.cpu` a `limits.processes`.
3. **Nulová síťová expozice řídicího rozhraní:**
   * `Incus` naslouchá výhradně na lokálním Unix socketu hostitele (žádné otevřené TCP API ani webové rozhraní do sítě). `ai` správce sítě jej ovládá lokálně přes `OpenTofu (latest)` a CLI `incus` se striktním auditem.
4. **Pravidlo krajní výjimky pro složité cizí balíky:**
   * Pokud by v budoucnu konkrétní nakoupený či open-source software vyžadoval vícekontejnerový `docker-compose` dodaný výrobcem, **nikdy se neinstaluje na hostitelský server `polarita-hq`**, ale spustí se výhradně uvnitř jedné vyhrazené, izolované instance v `Incus`.

### Tabulka výchozích limitů RAM po instancích (profil `MVP 64 GB`)

Hodnoty jsou výchozí a doladí se při přejímce; součet limitů instancí je nejvýše `52 GB` a hostitel s `ARC` nejvýše `12 GB` (dohromady nejvýše RAM přidělená VM `64 GB`). V profilu `MVP` neběží Windows VM, GPU ani plný `WhisperX` (přepis jen dávkově v noci na CPU). Dočasné instance (sestavovací instance, nedělní test obnovy) nemají vlastní řádek — běží mimo noční dávku `WhisperX` a sdílejí s ní její limit `4 GB`.

| Zóna | Instance | `limits.memory` | Vzniká v bloku |
| :--- | :--- | :---: | :---: |
| `dmz_edge` | `Caddy` | `0,5 GB` | `Blok 3` |
| `dmz_edge` | `CrowdSec` | `0,5 GB` | `Blok 3` |
| `dmz_edge` | `Headscale` | `0,5 GB` | `Blok 3` |
| `dmz_edge` | příchozí MX relay `Stalwart Mail` | `0,5 GB` | `Blok 3` |
| `data_vault` | `PostgreSQL` | `10 GB` | `Blok 5` |
| `data_vault` | `PgBouncer` | `0,25 GB` | `Blok 5` |
| `data_vault` | `Valkey` | `1,5 GB` | `Blok 5` |
| `data_vault` | `Garage` | `1,5 GB` | `Blok 5` |
| `data_vault` | `OpenBao` | `0,5 GB` | `Blok 4` |
| `data_vault` | `Vaultwarden` | `0,25 GB` | `Blok 4` |
| `app_internal` | `Keycloak` | `1,5 GB` | `Blok 5` |
| `app_internal` | `oauth2-proxy` | `0,25 GB` | `Blok 5` |
| `app_internal` | `Gitea` | `1 GB` | `Blok 5` |
| `app_internal` | `gitea-runner` | `1 GB` | `Blok 5` |
| `app_internal` | `Checkmk` | `1,5 GB` | `Blok 6` |
| `app_internal` | `Zulip` | `3,5 GB` | `Blok 7` |
| `app_internal` | `Paperclip` + CLI modelů | `2,5 GB` | `Blok 7` |
| `app_internal` | vlastní moduly Polarity (`metadata-schema-kernel` a další) | `2,5 GB` | `Bloky 7–11` |
| `app_internal` | `Nod` | `1 GB` | `Blok 7` |
| `app_internal` | `SilverBullet` | `0,25 GB` | `Blok 8` |
| `app_internal` | `Paperless-ngx` | `1,5 GB` | `Blok 8` |
| `app_internal` | `Vikunja` | `0,25 GB` | `Blok 8` |
| `app_internal` | weby `Astro` | `1 GB` | `Blok 9` |
| `app_internal` | `MedusaJS` | `1,5 GB` | `Blok 9` |
| `app_internal` | `Moodle` | `1,5 GB` | `Blok 9` |
| `app_internal` | `Umami` | `0,5 GB` | `Blok 9` |
| `app_internal` | pečetní modul `pyHanko` | `0,25 GB` | `Blok 4` |
| `dmz_edge` | instance stahovače signatur `ClamAV` | `0,25 GB` | `Blok 4` |
| `app_internal` | `Asterisk` | `1 GB` | `Blok 11` |
| `app_internal` | poštovní jádro `Stalwart Mail` | `1 GB` | `Blok 11` |
| `app_internal` | `Chatwoot CE` | `2,5 GB` | `Blok 11` |
| `app_internal` | `Traccar` | `0,75 GB` | `Blok 11` |
| `app_internal` | `comm-gateway` | `0,5 GB` | `Blok 11` |
| `sandbox_airgap` | karanténa `ClamAV` + čtení CAD/PDF | `2 GB` | `Blok 4` |
| `sandbox_airgap` | KVM VM `Dangerzone` | `2 GB` | `Blok 4` |
| `sandbox_airgap` | noční dávka `WhisperX` + `Silero VAD + librosa` | `4 GB` | `Blok 11` |
| **Součet instancí** | `dmz_edge` `2 GB` + `data_vault` `14 GB` + `app_internal` `27,5 GB` + `sandbox_airgap` `8 GB` | **`51,5 GB`** | — |
| **Hostitel** | `Ubuntu Server` + `OpenZFS ARC` (`zfs_arc_max`) + `Incus` | **nejvýše `12 GB`** | `Blok 1` |

### Matice povolených toků mezi zónami (zdroj → cíl → port)

Co v tabulce není, je zakázáno (`nftables` `default drop`). Konkrétní čísla portů se zapisují do `OpenTofu` při nasazení služby; tabulka určuje, které toky smějí vzniknout. Mezizónová pravidla `nftables` (`default drop` mezi mosty zón podle této matice) vznikají a testují se už v `Bloku 2`; `Blok 3` nad tento základ přidává veřejný perimetr a `CrowdSec`. Tok služby z pozdějšího bloku se zapíná a kladně ověřuje až v bloku, kde služba vzniká.

| Zdroj | Cíl | Port / protokol | Poznámka |
| :--- | :--- | :--- | :--- |
| internet | `Caddy` (`dmz_edge`) | `80/tcp`, `443/tcp+udp` | jediná veřejná HTTP/HTTPS služba (od `Bloku 3`) |
| internet | příchozí MX relay (`dmz_edge`) | `25/tcp` | od `Bloku 3` |
| internet | `Headscale` (`dmz_edge`) | `3478/udp` | STUN; řídicí bod `vpn.polarita.cz` jde přes `Caddy` (`443`) |
| protistrany `SIP Trunku` | přesměrování v `dmz_edge` → `Asterisk` (`app_internal`) | výslovně vyjmenovaný UDP rozsah médií (RTP) | až od `Bloku 11`; `0` příchozích SIP portů |
| IP whitelist M2M operátora | přesměrování v `dmz_edge` → `Traccar` (`app_internal`) | jeden TCP port zařízení | až od `Bloku 11`; nepoužije-li se M2M APN VPN |
| uzly `Headscale VPN` | `Caddy` (`dmz_edge`, adresa VPN) | `443/tcp` | interní vhosty `*.int.polarita.cz`; `Caddy` je uzlem VPN a interní vhosty obsluhuje jen na adrese VPN, požadavek s hlavičkou `Host` `*.int` z internetu odmítá |
| uzly `Headscale VPN` (správci) | hostitel `polarita-hq` | port `OpenSSH` | jen z VPN / LAN |
| `Caddy` (`dmz_edge`) | aplikace v `app_internal` | explicitně povolené aplikační porty | publikace storefrontů a interních vhostů |
| `Caddy` (`dmz_edge`) | `Vaultwarden` (`data_vault`) | port HTTP `Vaultwardenu` | výslovná výjimka: jen interní vhost dostupný z VPN |
| příchozí MX relay (`dmz_edge`) | poštovní jádro `Stalwart Mail` (`app_internal`) | jeden port trasy (`smtp` / `lmtp`) | až od `Bloku 11` |
| autorizované instance `app_internal` | `PostgreSQL` / `PgBouncer`, `Valkey`, `Garage` (`data_vault`) | porty těchto služeb | každá aplikace jen ke své databázi / koši |
| `OpenBao Agent` každé instance se síťovým rozhraním (`dmz_edge`, `app_internal`, `data_vault`) kromě `gitea-runner` | `OpenBao` (`data_vault`) | port API `OpenBao` | výslovná výjimka: vlastní identita `AppRole` každé takové instance; instance v `sandbox_airgap` nemají žádná strojová tajemství ani `OpenBao Agenta`; `gitea-runner` je z pravidla vyňat — nemá `AppRole`, `OpenBao Agenta` ani tok k `OpenBao` |
| `Checkmk` (`app_internal`) | hostitel, `dmz_edge`, `app_internal`, `data_vault` | port čtecího agenta | `data_vault` sonduje jen čtecím agentem |
| `Checkmk` (`app_internal`) | internet — API `Telegram` | odchozí `443/tcp` | jen out-of-band pager pro alerty |
| `Checkmk` (`app_internal`) | externí SMTP relay ze vstupů `Bloku 0` (jeden konkrétní hostitel) | odchozí submission port tohoto relay | druhý nezávislý kanál alertů od `Bloku 6`; jiný cíl na tomto portu se zahazuje |
| zálohovací klient (`polarita-hq`) | záložní uzel přes `Headscale VPN` | port `Restic REST Server` | jen `append-only` přístup |
| aplikace v `app_internal` | internet | odchozí `443/tcp` (a odchozí `SIPS/SRTP`, `25/tcp` pošty) | jen vyjmenované cíle (API modelů, rejstříky, `TSA`, `SIP Trunk`, kanály `Chatwoot`); ISDS a `Mapy.cz` mají vlastní jmenovité řádky níže; neplatí pro `gitea-runner`, který nemá žádný odchozí provoz |
| dočasná sestavovací instance (`dmz_edge`) | internet | odchozí `80/443/tcp` | jen po dobu sestavení obrazu |
| instance stahovače signatur `ClamAV` (`dmz_edge`) | distribuční služba signatur | odchozí `443/tcp` | od `Bloku 4`; do `sandbox_airgap` jdou signatury jen adresářem `clamav-db` připojeným pro čtení |
| `isds-podatelna-bridge` (`app_internal`) | testovací prostředí ISDS | odchozí `443/tcp` | od `Bloku 8`; produkční ISDS až po přepnutí v `Bloku 12` |
| `centralni-lhutnik-a-objekty` — dispečerský plánovač tras (`app_internal`) | `Mapy.cz Routing & Matrix API` (jmenovitý hostitel API zapsaný v `OpenTofu`) | odchozí `443/tcp` | od `Bloku 8`; od `Bloku 11` týž cíl i pro `fleet-gps-bridge`; jiný cíl se zahazuje |
| `gitea-runner` (`app_internal`) | `Gitea` (`app_internal`) | port HTTP `Gitea` | jediné povolené spojení runneru: žádný odchozí provoz do internetu ani do `data_vault` (ani k `OpenBao` — runner nemá žádná tajemství z trezoru, `AppRole` ani `OpenBao Agenta`); závislosti má v obrazu (offline wheelhouse, `Blok 5`) |
| `data_vault` | internet | — | žádný odchozí provoz |
| `sandbox_airgap` | cokoli | — | žádné síťové rozhraní, žádná strojová tajemství a žádný `OpenBao Agent`; jen připojené adresáře (`airgap-spool`, a pouze pro čtení `airgap-models` a `clamav-db`) |

### Sestavování obrazů pro zóny bez sítě a jediný tok do `sandbox_airgap`

* **Obrazy:** Instance v `data_vault` a `sandbox_airgap` nemají odchozí síť, a proto se v nich nic neinstaluje ani nestahuje. Jejich obrazy (balíčky, rozšíření, modely, `Dangerzone`) se sestavují v dočasné sestavovací instanci v `dmz_edge` s odchozím přístupem jen po dobu sestavení; hotový obraz se publikuje do místního úložiště obrazů `Incus` a instance se spouštějí z něj. Aktualizace = nové sestavení obrazu a výměna instance (měsíčně a při bezpečnostní záplatě). Počet zón zůstává `4`.
* **Jediný tok do `sandbox_airgap`:** karanténa `/srv/polarita/workspace/karantena` → `/srv/polarita/data/airgap-spool` (vstup) → zpracování → `/srv/polarita/data/airgap-spool` (výstup). Přesun provádí hostitelská jednotka `systemd`, ne aplikace. Modely (`/srv/polarita/data/airgap-models`) a signatury `ClamAV` (`/srv/polarita/data/clamav-db`) jsou do zóny připojeny pouze pro čtení.

---

## 3. Pokyny k instalaci a konfiguraci pro `ai` (Prompty)

**Zkouška při automatické instalaci.** Ověř lokální socket Incusu, ZFS a provider, nulový drift, start LXC, OCI a KVM a izolaci každé zóny. Dočasné instance označ a po zápisu výsledků odstraň. Níže uvedené kroky s živou protistranou či osobním vybavením jsou součástí produkční aktivace po převzetí.


> V režimu TEST proveď průzkum, ulož plán a automaticky nasaď a ověř změny. Použij testovací data a místní protějšky externích služeb. Skutečné osobní klíče, certifikáty a živé účty zapoj až po uživatelském testu a převzetí správcem.

### Prompt 1 — Průzkum, plán, instalace a bezpečná inicializace `Incus (latest)` a `OpenTofu (latest)` (`pro 17003 spravce-site`)

```text
V režimu TEST proveď instalaci samostatně. Kroky vyžadující osobní identitu nebo ostrý účet eviduj pro aktivaci po uživatelském testu a převzetí.
Jsi správce serveru (17003 spravce-site). Uvnitř VM polarita-hq s Ubuntu Server (latest LTS) připrav instalaci jednotné virtualizační vrstvy Incus (latest) a OpenTofu (latest) — bez instalace Dockeru na hostitele. Po inventuře proveď kroky 2–5 a ověř stav:

1. Preflight (Read-Only): Uvnitř VM ověř hostname polarita-hq, výsledek kvm z příkazu systemd-detect-virt, dostupnou RAM, vmx/svm a /dev/kvm. Ověř nftables, lokální socket vnitřního Incusu a stav případné předchozí inicializace. Před instalací je chybějící socket očekávaný. Ověř také, že zde neběží dockerd.
2. Instalace z ověřených zdrojů:
   - Přidej oficiální kryptograficky podepsaný stabilní repozitář Zabbly pro Incus a nainstaluj balíčky incus (včetně podpory QEMU/KVM a UEFI firmwaru pro plné virtuální stroje).
   - Přidej oficiální kryptograficky podepsaný repozitář OpenTofu a nainstaluj balíček tofu (latest).
   - V dokumentaci neuváděj pevná čísla verzí; při inicializaci OpenTofu uzamkni aktuální ověřený provider lxc/incus přes .terraform.lock.hcl.
3. Bezpečná neinteraktivní inicializace (incus admin init --preseed):
   - Pro vnitřní Incus připrav ovladač zfs nad prázdným datasetem data/incus z Bloku 1. V preseed zadej název datasetu podle zfs list uvnitř VM. Do něj patří výhradně svazky vnitřního Incusu. Vnější pool zrcadlo při tomto kroku spravuje nadále cluster.
   - Ponech řídicí API výhradně na lokálním Unix socketu (žádný síťový listener na TCP portu!).
   - Nastav oprávnění pro servisního správce s přísnou kontrolou u 17004 klicnik (běžný účet nemá přímý přístup k /dev/kvm mimo autorizovaný Incus socket).
4. Registruj v Incusu oficiální zdroje obrazů včetně vzdáleného registru pro nativní OCI kontejnery (--protocol oci pro docker.io a ghcr.io), abychom mohli spouštět i hotové aplikační obrazy bez Dockeru.
5. Ulož preseed konfiguraci do /srv/polarita/infra/incus/ a předlož výsledek kontroly agentovi 17004 klicnik.
```

### Prompt 2 — Deklarativní vytvoření 4 bezpečnostních síťových zón v `OpenTofu` (`pro 17003 spravce-site` + `17004 klicnik`)

```text
V režimu TEST proveď průzkum, ulož plán a automaticky nasaď a ověř změny. Použij testovací data a místní protějšky externích služeb. Skutečné osobní klíče, certifikáty a živé účty zapoj až po uživatelském testu a převzetí správcem.
Pomocí OpenTofu (latest) a provideru lxc/incus připrav ve složce /srv/polarita/infra/incus/zones/ deklarativní definici čtyř striktně oddělených prostředí na serveru polarita-hq:

1. Zóna 1 — dmz_edge: izolovaná síť a profil výhradně pro reverzní proxy Caddy (porty 80/tcp a 443/tcp+udp), řídicí server Headscale (+ 3478/udp STUN) a izolovaný příchozí SMTP MX relay port 25/tcp pro Stalwart Mail chráněný CrowdSec (jediná zóna přijímající veřejný příchozí provoz; žádné veřejné storefronty ani aplikační backendy, 0 příchozích SIP portů a 0 správních portů).
2. Zóna 2 — app_internal: interní aplikační a storefrontová síť (vč. všech storefrontů Astro, MedusaJS, Moodle, Keycloak, Zulip, Asterisk, Chatwoot CE, jádra Stalwart Mail, Paperclip, Gitea) s řízeným prostupem z dmz_edge pouze na explicitně povolené aplikační porty a s přísnými ACL pravidly (nftables).
3. Zóna 3 — data_vault: uzavřená databázová a trezorová síť s NULOVÝM přístupem do internetu (žádný odchozí NAT/egress ven ze serveru, přístup povolen výhradně podle matice toků: z autorizovaných aplikačních kontejnerů na konkrétní porty PostgreSQL/PgBouncer, Valkey a Garage, z OpenBao Agenta každé instance se síťovým rozhraním kromě gitea-runner na OpenBao, z Caddy na Vaultwarden jen pro interní vhost z VPN a z Checkmk jen na čtecího agenta).
4. Zóna 4 — sandbox_airgap: profil pro bez-síťové kontejnery a KVM virtuální stroje s výslovně odebraným síťovým rozhraním (v OpenTofu / Incus přepiš zděděný device { name = "eth0", type = "none" }, tj. eth0 none — nikdy neponechávej ani výchozí incusbr0!) a s předáváním souborů výhradně jediným tokem karanténa /srv/polarita/workspace/karantena -> spool /srv/polarita/data/airgap-spool (vstupní podsložka jen pro čtení ro) -> zpracování -> oddělený výstupní adresář spoolu, přičemž přesun provádí hostitelská jednotka systemd, ne aplikace; modely /srv/polarita/data/airgap-models a signatury ClamAV /srv/polarita/data/clamav-db připoj pouze pro čtení pro sanitizaci hlasových příloh WhisperX (HF_HUB_OFFLINE=1 + předstažené offline modely), ClamAV/Dangerzone a čtení cizích .dwg, .dxf, .ifc, .pdf, .xc4, příloh .zfo i historických šanonů ze služby 48h převzetí šanonů dle architektury CaMeL.
5. Ke každému profilu a instanci nastav v OpenTofu pevné limity paměti RAM (limits.memory), jader CPU (limits.cpu) a počtu procesů (limits.processes) podle tabulky výchozích limitů (v profilu MVP 64 GB součet limitů instancí nejvýše 52 GB a hostitel + zfs_arc_max nejvýše 12 GB; v Plném profilu 128 GB + GPU úměrně), aby žádná zacyklená služba nemohla vyčerpat prostředky hostitelského serveru.
6. Zapiš do OpenTofu matici povolených toků mezi zónami (zdroj -> cíl -> port; co v ní není, zahazuj) a po validaci ji už v tomto bloku nasaď jako mezizónová pravidla nftables (default drop mezi mosty zón podle matice; případný ufw odstraň, aby nevznikaly duplicitní tabulky; veřejný vstup z internetu zůstává do Bloku 3 zavřený — veřejný perimetr a CrowdSec přidá Blok 3 nad tento základ; toky služeb z pozdějších bloků, např. stahovač signatur ClamAV v dmz_edge -> distribuční služba signatur 443/tcp od Bloku 4, gitea-runner -> jen místní Gitea od Bloku 5, isds-podatelna-bridge -> testovací prostředí ISDS 443/tcp od Bloku 8 s produkčním ISDS až po přepnutí v Bloku 12 a centralni-lhutnik-a-objekty -> Mapy.cz Routing & Matrix API 443/tcp od Bloku 8, se zapínají až s danou službou), včetně výslovných výjimek (Caddy -> Vaultwarden jen interní vhost z VPN, OpenBao Agent každé instance se síťovým rozhraním -> OpenBao (instance v sandbox_airgap nemají žádná strojová tajemství ani agenta; gitea-runner z Bloku 5 je vyňat — nemá AppRole, agenta ani tok k OpenBao, jeho jediné spojení je místní Gitea), Checkmk -> data_vault jen čtecí agent, Checkmk -> API Telegram a -> jeden konkrétní externí SMTP relay ze vstupů Bloku 0 na jeho submission port, zálohovací klient -> záložní uzel přes VPN, Traccar a RTP Asterisk až v Bloku 11 přes přesměrování v dmz_edge).
7. Připrav definici dočasné sestavovací instance v dmz_edge (odchozí přístup jen po dobu sestavení) a postup: sestavení obrazu -> publikace do místního úložiště obrazů Incus -> spuštění instance v data_vault / sandbox_airgap z tohoto obrazu -> zrušení sestavovací instance; aktualizace = nové sestavení obrazu a výměna instance (měsíčně a při bezpečnostní záplatě).
8. Spusť tofu fmt, tofu validate a tofu plan. Ověř cíle a aplikuj uložený plán. Potvrď izolaci zón a nulový následný drift.
```

### Prompt 3 — Přejímací zkouška všech 3 režimů (`LXC`, `OCI`, `KVM VM`) a čistý úklid (`pro 17003 spravce-site`)

```text
V režimu TEST proveď průzkum, ulož plán a automaticky nasaď a ověř změny. Použij testovací data a místní protějšky externích služeb. Skutečné osobní klíče, certifikáty a živé účty zapoj až po uživatelském testu a převzetí správcem.
Proveď na serveru polarita-hq kompletní přejímací zkoušku virtualizační platformy Incus (latest) + OpenTofu (latest) ve všech třech režimech běhu:

1. Test 1 (Systémový kontejner LXC): Přes OpenTofu vytvoř neprivilegovaný kontejner Ubuntu (latest LTS), ověř jeho start, síťovou izolaci dle zóny, pořízení snapshotu a nulový drift (tofu plan vrátí beze změn).
2. Test 2 (Nativní OCI kontejner bez Dockeru): Ověř spuštění lehkého testovacího OCI obrazu přímo přes Incus OCI integraci bez přítomnosti démonu Docker na hostiteli.
3. Test 3 (Plný virtuální stroj KVM): Přes OpenTofu vytvoř testovací KVM virtuální stroj s hardwarovou akcelerací (/dev/kvm), ověř uvnitř hosta systemd-detect-virt = kvm a funkčnost v izolovaném profilu.
4. Test 4 (Obraz pro zónu bez sítě a matice toků): V dočasné sestavovací instanci v dmz_edge sestav zkušební obraz, publikuj jej do místního úložiště obrazů Incus, spusť z něj instanci v data_vault a ověř, že z ní nelze navázat spojení do internetu ani nepovolené mezizónové spojení (do dmz_edge a app_internal); ověř záporným testem i alespoň jeden tok mezi každou dvojicí zón, který v matici toků není (musí být zahozen). Povolené servisní výjimky (např. OpenBao Agent -> OpenBao, aplikace -> její databáze) se v Bloku 2 netestují — kladně se ověřují v bloku, kde služba vzniká. Sečti limits.memory všech definovaných instancí (součet + hostitel a ARC nejvýše RAM přidělená VM).
5. Povinný okamžitý úklid: Po úspěšném změření a zápisu protokolu zkoušky všechny cvičné instance včetně sestavovací čistě odstraň přes tofu destroy a ověř (incus list, incus storage volume list), že na serveru nezůstal žádný osiřelý testovací kontejner, virtuální stroj ani diskový svazek.
6. Ulož protokol přejímací zkoušky do /srv/polarita/workspace/dukazy/blok-02/ (do Vaultu se přenese až po jeho založení v Bloku 8).
```

---

## 4. Ověřitelné podmínky dokončení Bloku 2

- [ ] Na hostiteli `polarita-hq` běží **`Incus (latest)`** pouze na lokálním Unix socketu (žádný otevřený síťový port hypervizoru) a na hostiteli **není nainstalován Docker**.
- [ ] Hardwarová akcelerace `KVM` (`/dev/kvm`) je aktivní a ověřená skutečným startem plného virtuálního stroje.
- [ ] Fungují všechny tři režimy: systémové kontejnery (`LXC`), nativní aplikační obrazy (`OCI`) i plné virtuální stroje (`KVM`).
- [ ] V `OpenTofu (latest)` jsou definovány a ověřeny všechny 4 bezpečnostní zóny (`dmz_edge`, `app_internal`, `data_vault`, `sandbox_airgap`) a mezizónová pravidla `nftables` (`default drop` mezi mosty zón podle matice toků) jsou nasazena už v tomto bloku (veřejný perimetr a `CrowdSec` přidává `Blok 3`); zóna `data_vault` je z internetu nedosažitelná a kontejner v `sandbox_airgap` nemá žádné síťové rozhraní (`ip link` ukáže pouze `lo`).
- [ ] Matice povolených toků mezi zónami je zapsána v `OpenTofu` včetně výslovných výjimek a záporné testy (spojení do internetu z `data_vault` a nepovolená mezizónová spojení mimo matici) skončily zahozením; povolené servisní výjimky se kladně ověřují až v bloku, kde služba vzniká.
- [ ] Součet `limits.memory` všech definovaných instancí je v profilu `MVP` nejvýše `52 GB` a spolu s hostitelem a `ARC` (nejvýše `12 GB`) nepřesahuje RAM přidělenou VM.
- [ ] Je ověřena cesta sestavení obrazu pro zóny bez sítě: obraz sestavený v dočasné sestavovací instanci v `dmz_edge` byl publikován do místního úložiště obrazů `Incus` a instance z něj spuštěná v `data_vault` nenaváže spojení do internetu ani nepovolené mezizónové spojení.
- [ ] Po přejímacích testech nezůstaly v systému žádné dočasné ani nepojmenované instance (včetně sestavovací).
