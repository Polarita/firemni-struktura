# 03 — Síť, privátní mesh VPN, správa DNS, firewall, reverzní proxy a poštovní/SIP hrana · Verze 2.7

Tento dokument definuje síťovou vrstvu společnosti **Polarita s.r.o.** — oddělení veřejného provozu zákazníků od privátní firemní sítě pro jednatele (`1001`), spolupracovníky (`1002+`) a pobočky (`101`–`999`), bezpečnou hranu poštovního serveru **`Stalwart Mail`** a odchozí registraci ústředny **`Asterisk`** bez veřejných příchozích SIP portů, centralizovanou správu všech domén a vícevrstvou ochranu bez licenčních poplatků za uživatele.

---

## 1. Seznam vybraného softwaru

| Oblast | Vybraný software | Kanál / Režim | Role a použití v Polarita s.r.o. (Verze 2.7) | Odpovědný `ai` / garant |
| :--- | :--- | :--- | :--- | :--- |
| **Správa veřejného DNS a ochrana domén** | **Cloudflare DNS** | `Standard / Free` *(řízeno přes API a `OpenTofu`)* | Centrální správa všech firemních domén (`polarita.cz`, `polarita.eu` a dalších) v jednom účtu zdarma, podpora `DNSSEC`, `CAA`, `SPF`, `DKIM`, `DMARC`, `MTA-STS`, DDoS ochrany veřejných webů a omezených API tokenů pro automatické vystavování HTTPS certifikátů (`DNS-01`). | `17003` `spravce-site` *(kontrola `17004` `klicnik`)* |
| **Veřejná reverzní proxy a HTTPS (`dmz_edge`)** | **Caddy** *(s DNS modulem Cloudflare)* | `latest` *(v izolovaném kontejneru `Incus`)* | Služba vystavená do veřejného internetu na portech `80` a `443` v zóně `dmz_edge` (spolu s odděleným příchozím MX relayem **`Stalwart Mail`**). Automaticky obstarává TLS certifikáty a směruje provoz na veřejný web (vč. widgetu `Chatwoot CE` `WebChat`), e-shop, Akademii a veřejné QR karty objektů. | `17003` `spravce-site` *(spolupráce `17002` `webmaster`)* |
| **Privátní šifrovaná mesh VPN (servery, pobočky `101+`, PC, mobily)** | **Headscale** *(+ volitelné webové rozhraní **Headplane**)* | `latest` *(vlastní self-hosted server, nezávislý na cizím cloudu)* | Plně vlastní open-source řídicí server šifrované WireGuard mesh sítě (včetně vlastního vestavěného DERP relay převaděče, MagicDNS, subnet routingu pro pobočky a centrální ACL politiky v souboru). Nese interní `Zulip`, `WebRTC` softphone, registraci klientů `Linphone` (`SIPS/SRTP`) i `JMAP / IMAP IDLE / ManageSieve` pošty na **Windows**, **Linux**, **Apple macOS**, **Android** i **Apple iOS / iPadOS**. | `17003` `spravce-site` *(audit ACL `17004` `klicnik`)* |
| **Jaderný a zónový firewall (+ nulový veřejný SIP port)** | **nftables** | `latest` *(nativní součást jádra `Ubuntu Server LTS`)* | Jediný zdroj pravdy pro paketovou filtraci na fyzickém síťovém rozhraní, na privátním VPN rozhraní i mezi 4 bezpečnostními zónami v `Incus`. **Ústředna `Asterisk` se k českému SIP Trunk operátorovi registruje výhradně odchozím šifrovaným spojením `SIPS / SRTP` (`0` veřejných příchozích portů `5060/5061` z internetu!).** | `17003` `spravce-site` *(audit `17004` `klicnik`)* |
| **Aktivní obrana veřejné hrany (IPS)** | **CrowdSec** *(+ bouncer pro `Caddy`, `Stalwart Mail` a `nftables`)* | `latest` | Průběžně čte přístupové logy reverzní proxy a poštovní hrany v `dmz_edge` a automaticky blokuje botnety, skenery zranitelností a útoky hrubou silou dříve, než zatíží aplikační zónu. | `17004` `klicnik` / `17003` `spravce-site` |
| **Vzdálená správa** | **OpenSSH** | `latest` | `OpenSSH` naslouchá výhradně v privátní VPN/LAN (nikdy do veřejného internetu, pouze klíče `Ed25519`). | `17003` `spravce-site` |

---

## 2. Architektonická pravidla a zdůvodnění výběru

1. **Dvě přísně oddělené cesty do firmy a nulový veřejný SIP port (`K1`, `K3`, `K4`):**
   * **Veřejná cesta (`Cloudflare` → `Caddy` a MX relay `Stalwart Mail` v `dmz_edge`):** Pouze pro zákazníky a veřejné služby (`polarita.cz` včetně Kalkulačky rizik SVJ `/kalkulacka-svj`, karanténní brány `/prevzeti-sanonu`, veřejného náhledu QR štítku rozváděče `/objekt/<token>` a `WebChat` widgetu `Chatwoot CE`, `polarita.eu`, `akademie.polarita.cz`, webhook `WhatsApp Business`, příchozí MX pošta `Stalwart Mail` a řídicí bod `vpn.polarita.cz` pro výměnu klíčů `Headscale`). **Softwarová ústředna `Asterisk` nikdy nevystavuje veřejný příchozí SIP port do internetu** — registruje se odchozím `SIPS / SRTP` spojením k českému SIP Trunk operátorovi, čímž zcela eliminuje VoIP toll-fraud skenery.
   * **Privátní cesta (`Headscale` mesh VPN):** Schvalovací fronta `Decisions` (`mutation_confirm`), **360° Karta spisu s tlačítky `„Pracuj“` a `WebRTC` softphonem**, interní týmový hub **`Zulip`** + `LiveKit`, klientský přístup k poště **`Stalwart Mail`** (`JMAP / IMAP IDLE / ManageSieve`) a softphonům **`Linphone`**, interní operátorský inbox **`Chatwoot CE` (dodatečně chráněný reverzní proxy `Caddy + oauth2-proxy` s `Keycloak OIDC forward-auth`)**, sdílená paměť `Vault`, lokální Git/CI server `Gitea`, administrace `Umami`, interní účetní/HR/skladové nástroje, monitoring `Checkmk` i `OpenSSH` **nejsou nikdy vystaveny do veřejného internetu**. Jednatel (`1001`) i oprávnění spolupracovníci (`1002+`) k nim přistupují z počítačů i mobilů výhradně skrz šifrovanou mesh VPN.
2. **Plná suverenita a nulové poplatky za lidi díky `Headscale (latest)`:**
   * Nepoužíváme komerční cloud ani účet u firmy Tailscale — seznam serverů, poboček (`101`–`999`), zařízení ani přístupová pravidla nikdy neopouštějí server Polarity a neplatí se žádný měsíční paušál za přidané uživatele.
   * Uzly komunikují napřímo mezi sebou nejkratší šifrovanou cestou (peer-to-peer WireGuard mesh). Pro případy přísných mobilních operátorů nebo hotelových sítí má `Headscale` zapnutý **vlastní vestavěný DERP relay** na HTTPS portu `443`.
   * Na klientských zařízeních (**Windows**, **Linux**, **Apple macOS**, **Android**, **Apple iOS / iPadOS**) se používá odladěná open-source klientská aplikace namířená parametrem *Alternate Server URL* přímo na `https://vpn.polarita.cz`, vždy se zakázaným vestavěným VPN SSH (`RunSSH=false`).
3. **Jednotná správa více domén v `Cloudflare DNS`:**
   * Globální domény (`.com`, `.net`, `.org`, `.online` apod.) lze vést přímo u Cloudflare za velkoobchodní cenu bez marže; národní domény `.cz` a `.eu` zůstávají registrovány u českého registrátora s jmennými servery (NS) namířenými na Cloudflare.
   * Režim záznamů se volí cíleně: **oranžový štít (Proxy/DDoS ochrana)** pro veřejné weby a e-shop, **čisté DNS (DNS-only)** pro poštu (`MX`, `SPF`, `DKIM`, `DMARC`) a přímé koncové body VPN (`vpn.polarita.cz`).
   * Veškeré DNS záznamy spravuje deklarativně `OpenTofu (latest)` přes přísně omezený API token uložený do spuštění `OpenBao` dočasně v `systemd-creds` (TPM) na hostiteli; v `Bloku 4` se token přesune do trezoru `OpenBao` a zrotuje (viz Blok `04`).
4. **Čistý jaderný firewall `nftables` (včetně ochrany VPN rozhraní):**
   * Na hostiteli se nepoužívá `ufw` ani `iptables`. Samotné připojení stroje do VPN neznamená automatickou důvěru ke všem portům — `nftables` explicitně filtruje příchozí pakety i na rozhraní VPN a povoluje jen schválené služby dle matice oprávnění.

---

## 3. Pokyny k instalaci a konfiguraci pro `ai` (Prompty)

### Prompt 1 — Bezvýpadkový převod domén do `Cloudflare DNS` a správa přes `OpenTofu` (`pro 17003 spravce-site` + `17004 klicnik`)

```text
Jsi správce sítě (17003 spravce-site). Připrav bezvýpadkový převod správy DNS firemních domén (polarita.cz, polarita.eu a souvisejících domén) pod Cloudflare DNS a jejich deklarativní správu v OpenTofu (latest):

1. Inventura před změnou (Read-Only):
   - Vypiš a archivuj kompletní současnou DNS zónu každé domény (A, AAAA, CNAME, MX, TXT včetně SPF/DKIM/DMARC, SRV, CAA) a ověř aktuální stav DNSSEC u registrátora.
2. Příprava v Cloudflare a OpenTofu:
   - Připrav v /srv/polarita/infra/dns/ deklarativní konfiguraci OpenTofu (provider cloudflare) obsahující 100 % stávajících záznamů.
   - U veřejného webu a e-shopu navrhni režim DDoS/WAF ochrany, u poštovních záznamů a řídicího subdoménového záznamu vpn.polarita.cz striktně nastav režim čistého DNS (proxied = false).
   - Nastav CAA záznamy omezující vydávání certifikátů pouze na schválené certifikační autority.
   - Vyžádej pro automatizaci pouze úzce vymezený Cloudflare API token (oprávnění výhradně Zone:DNS:Edit pro vybrané zóny, žádné globální práva k účtu!).
3. Postup přepnutí bez výpadku (pro schválení v Decisions):
   - Pokud je u stávajícího registrátora aktivní DNSSEC, vypiš přesný krok vypnutí DS záznamu a bezpečnou čekací lhůtu TTL před přepsáním NS serverů na Cloudflare, a následné zapnutí DNSSEC v Cloudflare po propagaci.
4. Nech kompletní plán a diff DNS záznamů zkontrolovat agentem 17004 klicnik a předlož jej ke schválení vlastníkovi (1001) do Decisions.
```

### Prompt 2 — Reverzní proxy `Caddy (latest)`, `CrowdSec (latest)` a firewall `nftables (latest)` (`pro 17003 spravce-site` + `17004 klicnik`)

```text
Po schválení v Decisions nasaď na serveru polarita-hq síťovou ochranu hostitele a veřejnou hranu v zóně dmz_edge (v dokumentaci bez čísel verzí; nasazené verze a digesty uzamkni v lockfilech):

1. Hostitelský a zónový firewall nftables (latest):
   - Odstraň případný ufw, aby nevznikaly duplicitní tabulky, a nastav čistý deklarativní ruleset nftables (/etc/nftables.conf + pravidla zón Incus).
   - Z veřejného internetu povol výhradně porty 80/tcp a 443/tcp+udp (HTTP/3) směrované do kontejneru reverzní proxy Caddy v zóně dmz_edge a port 25/tcp směrovaný výhradně na izolovaný příchozí SMTP MX relay serveru Stalwart Mail v zóně dmz_edge — kontejner relay vytvoř přes OpenTofu již v tomto bloku výhradně v roli příchozího SMTP relay bez schránek a bez externí databáze (jen vestavěné lokální úložiště RocksDB pro konfiguraci a frontu, bez přístupu do data_vault; do nasazení poštovního jádra v Bloku 11 nepřijímá poštu pro žádnou doménu — ověřuje se jen dostupnost portu 25, STARTTLS a logy pro CrowdSec; ostré MX záznamy se přepínají až v Bloku 12) (vestavěný DERP řídicího serveru Headscale běží výhradně přes HTTPS 443 za Caddy bez samostatného veřejného STUN/WireGuard portu; 0 příchozích SIP portů 5060/5061 a 0 veřejných klientských IMAP/JMAP/Submise portů!).
   - Na rozhraní privátní VPN zaveď explicitní input filtr (povol jen autorizované správcovské a interní porty dle ACL, vše ostatní zahazuj).
   - Port OpenSSH nesmí být dostupný z veřejného internetu — do ověření spojení přes Headscale (Prompt 3) spravuj server pouze z konzole / LAN, poté výhradně uvnitř VPN!
2. Reverzní proxy Caddy (latest) v zóně dmz_edge:
   - Vytvoř přes OpenTofu v zóně dmz_edge izolovaný neprivilegovaný kontejner v Incusu a nainstaluj Caddy (latest) s modulem pro Cloudflare DNS-01.
   - Nastav automatické vystavování a obnovu TLS certifikátů (včetně interních subdomén přes DNS-01 výzvu bez otevírání interních služeb do internetu), přesměrování HTTP -> HTTPS a přísné hlavičky (HSTS, X-Content-Type-Options, Referrer-Policy, Content-Security-Policy).
3. Aktivní ochrana CrowdSec (latest):
   - Nasaď CrowdSec čtoucí strukturované JSON logy z Caddy i logy příchozího SMTP MX relay Stalwart Mail a napoj bouncer pro automatické blokování útočících IP adres v nftables.
4. Ověř zvenčí skenem portů, že mimo porty 80/443, příchozí MX relay 25/tcp server neodpovídá na žádný jiný port (0 příchozích SIP portů, 0 klientských IMAP/JMAP portů, 0 SSH/DB portů), a předej protokol kontroly agentovi 17004 klicnik.
```

### Prompt 3 — Vlastní mesh VPN `Headscale (latest)` pro centrálu, pobočky (`101+`), PC a mobily (`pro 17003 spravce-site` + `17004 klicnik`)

```text
Nasaď a nakonfiguruj vlastní self-hosted řídicí server privátní mesh VPN Headscale (latest) na doméně vpn.polarita.cz:

1. Nasazení Headscale (latest) v Incus:
   - Vytvoř přes OpenTofu dedikovaný kontejner pro Headscale (latest) v zóně dmz_edge (volitelně s interním přehledovým rozhraním Headplane dostupným výhradně z privátní VPN) a zpřístupni řídicí endpoint https://vpn.polarita.cz přes reverzní proxy Caddy (v Cloudflare DNS striktně v režimu čistého DNS bez proxy).
   - Zapni v Headscale vestavěný vlastní DERP relay server, aby i nouzové přeposílání šifrovaného provozu za přísnými firewally operátorů probíhalo výhradně přes server Polarity bez závislosti na cizích serverech.
   - Nastav interní jmenný prostor MagicDNS (např. interní doménu sítě Polarita) a ukládej lokální export databáze a konfigurace Headscale do /srv/polarita/backups/ (do pravidelných off-site záloh se zapojí v Bloku 6).
2. Bezpečnostní politika ACL jako kód:
   - Vytvoř soubor politiky ACL (/srv/polarita/infra/headscale/acl.hujson) rozlišující role: vlastník/jednatel (1001), správci IT (17003/17004), běžní spolupracovníci (1002+), pobočkové routery (101–999) a produkční servery.
   - Zakaž vestavěné VPN SSH (žádné přepisování systémového OpenSSH; na všech serverech vynucuj RunSSH=false).
3. Multiplatformní připojení klientů (Windows, Linux, Apple macOS, Android, Apple iOS / iPadOS):
   - Připrav stručný, srozumitelný návod do /srv/polarita/vault/07-IT-a-Architektura/ (včetně postupu zadání Alternate Server URL https://vpn.polarita.cz na iPhonu, Androidu, Windows, macOS a Linuxu) a otestuj přímé peer-to-peer mesh spojení i záložní přenos přes vlastní DERP.
4. Nech ACL politiku i konfiguraci zkontrolovat u 17004 klicnik (VERIFIED_PASS) před připojením produkčních uzlů.
```

---

## 4. Ověřitelné podmínky dokončení Bloku 3

- [ ] Všechny firemní domény mají DNS spravované přes **`Cloudflare DNS`** v `OpenTofu` se zapnutým `DNSSEC`, `CAA` a úzce omezeným API tokenem.
- [ ] Z veřejného internetu naslouchá v zóně `dmz_edge` výhradně reverzní proxy **`Caddy (latest)`** (`80/443`) a izolovaný příchozí SMTP MX relay **`Stalwart Mail`** (`25/tcp`), obojí chráněné nástrojem **`CrowdSec (latest)`** a jaderným firewallem **`nftables (latest)`** (`0` příchozích SIP portů `5060/5061`, `0` veřejných klientských IMAP/JMAP/Submise portů).
- [ ] **`OpenSSH (latest)`** ani žádné interní rozhraní (`Decisions`, `Vault`, databáze, správa) není dostupné z veřejného internetu.
- [ ] Běží vlastní mesh VPN **`Headscale (latest)`** s vlastním vestavěným DERP relay (nulová závislost na cloudu Tailscale, `0 Kč` za neomezený počet uživatelů a poboček `101`–`999`).
- [ ] Připojení do privátní VPN je ověřeno na stanicích (**Windows**, **Linux**, **Apple macOS**) i telefonech (**Android**, **Apple iOS / iPadOS**).
