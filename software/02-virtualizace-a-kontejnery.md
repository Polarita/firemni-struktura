# 02 — Virtualizace, kontejnerizace a izolace zón (Bez Dockeru na hostiteli) · Verze 2.7

Tento dokument stanovuje jednotnou virtualizační a kontejnerovou platformu na centrálním serveru `polarita-hq` (`Ubuntu Server — latest LTS`) pro provoz všech aplikací, databází, komunikační ústředny, bez-síťové karantény i testů obnovy společnosti **Polarita s.r.o.**

---

## 1. Seznam vybraného softwaru

| Komponenta | Vybraný software | Kanál / Zdroj | Role a použití v Polarita s.r.o. (Verze 2.7) | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Jednotný správce virtuálních strojů a kontejnerů** | **Incus** | `latest` *(oficiální podepsaný stabilní repozitář Zabbly)* | Spouští pod jedním nástrojem plné virtuální stroje (`KVM`), lehké systémové kontejnery (`LXC`) i hotové aplikační obrazy (`OCI` přímo z Docker Hubu / GHCR) — zcela bez nutnosti instalovat Docker na hostitele. | `17003` `spravce-site` *(kontrola `17004` `klicnik`)* |
| **Hardwarová virtualizace plných VM** | **QEMU / KVM** *(s UEFI OVMF)* | `latest` *(ovládáno přímo přes `Incus`)* | Hardwarově oddělené virtuální stroje pro bez-síťový sandbox (`sandbox_airgap` — výkresy, přílohy `.zfo`, hlasové zprávy a přílohy z `Chatwoot CE / Stalwart Mail` i 48h převzetí šanonů `N7`), čtvrtletní *Full DR Drill* obnovy záloh a případnou izolovanou Windows VM pro oborový elektro software. | `17003` `spravce-site` |
| **Deklarativní správa infrastruktury (IaC)** | **OpenTofu** + provider **`lxc/incus`** | `latest` *(oficiální podepsaný balíček a uzamčený provider)* | Veškeré sítě, profily, úložiště, kontejnery (vč. `Asterisk`, `WhisperX`, `Zulip`, `Stalwart Mail`, `Chatwoot CE`, `LiveKit`) i virtuální stroje vytváří a spravuje `ai` agent deklarativně v souborech `.tf` (auditovatelný plán před každou změnou, kontrola odchylek `drift`). | `17003` `spravce-site` *(revize `17004` `klicnik`)* |

---

## 2. Architektonická pravidla a proč nepoužíváme Docker na hostiteli

1. **Jeden nástroj místo tří (`Incus latest` pokrývá všechny tři režimy běhu):**
   * **Režim A — Systémové kontejnery (`LXC`):** Lehké izolované instance `Ubuntu (latest LTS)` s minimální režií paměti RAM pro databáze, reverzní proxy, weby, e-shop, Akademii, softwarovou ústřednu **`Asterisk`**, přepisový worker **`WhisperX`**, týmový **`Zulip`**, poštovní **`Stalwart Mail`**, omnichannel **`Chatwoot CE`** a interní služby. Spravují se čitelně jako běžný Linux a zálohují jedním příkazem.
   * **Režim B — Nativní aplikační kontejnery (`OCI` bez Dockeru):** `Incus (latest)` umí přes protokol `oci` přímo stahovat a spouštět hotové aplikační obrazy z veřejných registrů (`docker.io`, `ghcr.io`). Není tak potřeba instalovat démon `Docker` ani `containerd` na hlavní server.
   * **Režim C — Plné virtuální stroje (`KVM VM`):** Vlastní jádro a plná hardwarová izolace přes `/dev/kvm`. Používá se všude tam, kde je nutná nejvyšší bezpečnostní zeď (otevírání cizích příloh, hlasových zpráv a výkresů `.dwg`/`.pdf`/`.xc4`), čistá VM pro čtvrtletní *Full Bare-Metal / VM DR Drill* (týdenní nedělní test obnovy v `03:00` běží v odpojeném kontejneru) nebo běh jiného operačního systému (např. Windows VM přístupná ze stanic Windows, Linux i Apple macOS).
2. **Čistý firewall a čtyři síťové zóny bez kolizí:**
   * Vynecháním Dockeru na hostitelském serveru odpadá přepisování firewallu démonem Dockeru. Všechny 4 síťové zóny firmy spravuje jednotně `Incus (latest)` nad jaderným `nftables`:
     1. `dmz_edge` — veřejná hrana (reverzní proxy `Caddy` pro příchozí HTTPS provoz, řídicí server `Headscale` a příchozí MX relay `Stalwart Mail`; **nulový veřejný příchozí SIP port**),
     2. `app_internal` — aplikační a komunikační vrstva webů, e-shopu, Akademie, portálu, ústředny `Asterisk`, `Zulip`, `Chatwoot CE`, `comm-gateway` a `ai` orchestrátoru,
     3. `data_vault` — izolovaná databázová a trezorová komora **bez přístupu do internetu**,
     4. `sandbox_airgap` — zcela odpojené prostředí **bez síťového rozhraní** pro bezpečné čtení nedůvěryhodných cizích souborů a hlasových zpráv (princip `Spoken & Text CaMeL`) a pro lokální přepis `WhisperX` + akustickou urgenci `Silero VAD + librosa`.
3. **Nulová síťová expozice řídicího rozhraní:**
   * `Incus` naslouchá výhradně na lokálním Unix socketu hostitele (žádné otevřené TCP API ani webové rozhraní do sítě). `ai` správce sítě jej ovládá lokálně přes `OpenTofu (latest)` a CLI `incus` se striktním auditem.
4. **Pravidlo krajní výjimky pro složité cizí balíky:**
   * Pokud by v budoucnu konkrétní nakoupený či open-source software vyžadoval vícekontejnerový `docker-compose` dodaný výrobcem, **nikdy se neinstaluje na hostitelský server `polarita-hq`**, ale spustí se výhradně uvnitř jedné vyhrazené, izolované instance v `Incus`.

---

## 3. Pokyny k instalaci a konfiguraci pro `ai` (Prompty)

### Prompt 1 — Instalace a bezpečná inicializace `Incus (latest)` a `OpenTofu (latest)` (`pro 17003 spravce-site`)

```text
Jsi správce serveru (17003 spravce-site). Na čistém serveru polarita-hq s Ubuntu Server (latest LTS) připrav a po schválení v Decisions proveď instalaci jednotné virtualizační vrstvy Incus (latest) a OpenTofu (latest) — bez instalace Dockeru na hostitele:

1. Preflight (Read-Only): Ověř, že v BIOS/UEFI je zapnutá hardwarová virtualizace (příznaky vmx nebo svm, přítomnost /dev/kvm; na náhradní variantě pronajatého virtuálního stroje vnořená virtualizace — není-li dostupná, pokračuj pouze s kontejnery LXC a OCI). Dále ověř, že funguje nftables a na hostiteli neběží kolidující démon dockerd.
2. Instalace z ověřených zdrojů:
   - Přidej oficiální kryptograficky podepsaný stabilní repozitář Zabbly pro Incus a nainstaluj balíčky incus (včetně podpory QEMU/KVM a UEFI firmwaru pro plné virtuální stroje).
   - Přidej oficiální kryptograficky podepsaný repozitář OpenTofu a nainstaluj balíček tofu (latest).
   - V dokumentaci neuváděj pevná čísla verzí; při inicializaci OpenTofu uzamkni aktuální ověřený provider lxc/incus přes .terraform.lock.hcl.
3. Bezpečná neinteraktivní inicializace (incus admin init --preseed):
   - Nastav úložiště (storage pool s ovladačem zfs nad existujícím prázdným datasetem data/incus z Bloku 1 — v preseed zapiš source jako název datasetu ZFS bez úvodního lomítka (tvar <zpool>/…/data/incus podle výpisu zfs list), nikdy jako cestu /srv/polarita/data/incus; dataset patří výhradně Incusu a nesmí obsahovat cizí soubory ani podřízené datasety — u fyzického stroje, příp. blokový pool lvm s thin-provisioningem u cloudového VPS pro podporu atomických snapshotů).
   - Ponech řídicí API výhradně na lokálním Unix socketu (žádný síťový listener na TCP portu!).
   - Nastav oprávnění pro servisního správce s přísnou kontrolou u 17004 klicnik (běžný účet nemá přímý přístup k /dev/kvm mimo autorizovaný Incus socket).
4. Registruj v Incusu oficiální zdroje obrazů včetně vzdáleného registru pro nativní OCI kontejnery (--protocol oci pro docker.io a ghcr.io), abychom mohli spouštět i hotové aplikační obrazy bez Dockeru.
5. Ulož preseed konfiguraci do /srv/polarita/infra/incus/ a předlož výsledek kontroly agentovi 17004 klicnik.
```

### Prompt 2 — Deklarativní vytvoření 4 bezpečnostních síťových zón v `OpenTofu` (`pro 17003 spravce-site` + `17004 klicnik`)

```text
Pomocí OpenTofu (latest) a provideru lxc/incus připrav ve složce /srv/polarita/infra/incus/zones/ deklarativní definici čtyř striktně oddělených prostředí na serveru polarita-hq:

1. Zóna 1 — dmz_edge: izolovaná síť a profil pro reverzní proxy Caddy (porty 80 a 443), řídicí server Headscale a izolovaný příchozí SMTP MX relay port 25/tcp pro Stalwart Mail chráněný CrowdSec (jediná zóna přijímající veřejný příchozí provoz; 0 příchozích SIP a 0 správních portů).
2. Zóna 2 — app_internal: interní aplikační síť s řízeným prostupem z dmz_edge pouze na explicitně povolené aplikační porty a s přísnými ACL pravidly (nftables).
3. Zóna 3 — data_vault: uzavřená databázová a trezorová síť s NULOVÝM přístupem do internetu (žádný odchozí NAT/egress ven ze serveru, přístup povolen výhradně z autorizovaných aplikačních kontejnerů na konkrétní porty databází).
4. Zóna 4 — sandbox_airgap: profil pro bez-síťové kontejnery a KVM virtuální stroje bez jakéhokoliv síťového rozhraní (nic = none v Incus — pouze lokální kontrolované předání souborů (vstupní adresář z karantény jen pro čtení, oddělený výstupní adresář pro výsledky) pro sanitizaci hlasových příloh WhisperX a čtení cizích .dwg, .dxf, .ifc, .pdf, .xc4, příloh .zfo i historických šanonů ze služby 48h převzetí šanonů dle architektury CaMeL).
5. Ke každému profilu nastav výchozí bezpečnostní limity paměti RAM, jader CPU a počtu procesů, aby žádná zacyklená služba nemohla vyčerpat prostředky hostitelského serveru.
6. Spusť tofu fmt, tofu validate a tofu plan, nech síťová ACL pravidla zkontrolovat u 17004 klicnik (VERIFIED_PASS) a předlož plán ke schválení do Decisions před spuštěním tofu apply.
```

### Prompt 3 — Přejímací zkouška všech 3 režimů (`LXC`, `OCI`, `KVM VM`) a čistý úklid (`pro 17003 spravce-site`)

```text
Proveď na serveru polarita-hq kompletní přejímací zkoušku virtualizační platformy Incus (latest) + OpenTofu (latest) ve všech třech režimech běhu:

1. Test 1 (Systémový kontejner LXC): Přes OpenTofu vytvoř neprivilegovaný kontejner Ubuntu (latest LTS), ověř jeho start, síťovou izolaci dle zóny, pořízení snapshotu a nulový drift (tofu plan vrátí beze změn).
2. Test 2 (Nativní OCI kontejner bez Dockeru): Ověř spuštění lehkého testovacího OCI obrazu přímo přes Incus OCI integraci bez přítomnosti démonu Docker na hostiteli.
3. Test 3 (Plný virtuální stroj KVM): Přes OpenTofu vytvoř testovací KVM virtuální stroj s hardwarovou akcelerací (/dev/kvm), ověř uvnitř hosta systemd-detect-virt = kvm a funkčnost v izolovaném profilu.
4. Povinný okamžitý úklid: Po úspěšném změření a zápisu protokolu zkoušky všechny tři cvičné instance čistě odstraň přes tofu destroy a ověř (incus list, incus storage volume list), že na serveru nezůstal žádný osiřelý testovací kontejner, virtuální stroj ani diskový svazek.
5. Ulož protokol přejímací zkoušky do sdílené paměti (/srv/polarita/vault/07-IT-a-Architektura/).
```

---

## 4. Ověřitelné podmínky dokončení Bloku 2

- [ ] Na hostiteli `polarita-hq` běží **`Incus (latest)`** pouze na lokálním Unix socketu (žádný otevřený síťový port hypervizoru) a na hostiteli **není nainstalován Docker**.
- [ ] Hardwarová akcelerace `KVM` (`/dev/kvm`) je aktivní a ověřená skutečným startem plného virtuálního stroje.
- [ ] Fungují všechny tři režimy: systémové kontejnery (`LXC`), nativní aplikační obrazy (`OCI`) i plné virtuální stroje (`KVM`).
- [ ] V `OpenTofu (latest)` jsou definovány a ověřeny všechny 4 bezpečnostní zóny (`dmz_edge`, `app_internal`, `data_vault`, `sandbox_airgap`) se striktními ACL v `nftables`; zóna `data_vault` je z internetu nedosažitelná a kontejner v `sandbox_airgap` nemá žádné síťové rozhraní (`ip link` ukáže pouze `lo`).
- [ ] Po přejímacích testech nezůstaly v systému žádné dočasné ani nepojmenované instance.
