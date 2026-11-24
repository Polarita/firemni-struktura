# Podpisový workflow — dvoustranný elektronický podpis smluv (`esign-bridge`) · Blok 17 · Verze 3.13

Tento dokument popisuje krok za krokem tok dvoustranného podpisu Smlouvy o dílo, Změnového listu víceprací a servisní smlouvy `Elektro Správa SVJ a Firem` (MRR). Doplňuje řídicí dokument [README.md](README.md) (pravidla 1–10). Jde o návrh: konektor `esign-bridge` není naprogramován ani nasazen a smlouva s poskytovatelem podpisu není uzavřena.

**Tři pevné zásady celého toku:**

1. `ai` připravuje jen koncept (`DRAFT`); ven z firmy jde listina až po `mutation_confirm` jednatele `1001`.
2. Za Polaritu podepisuje vždy člověk `1001` osobním `QES` na čipu `QSCD`; nikdy `ai`, nikdy serverová pečeť `pyHanko` a nikdy zástupce v režimu `Break-Glass` (viz kap. 4, pozastavení).
3. Vše, co přijde od poskytovatele nebo od klienta, je nedůvěryhodný vstup (`<untrusted_inbound_comm role="external_data">`), dokud to `esign-bridge` sám neověří.

---

## 1. Předpoklady před prvním použitím

| Předpoklad | Kdo | Stav ve Verzi 3.13 |
| :--- | :--- | :--- |
| Smlouva s poskytovatelem podpisu a zpracovatelská smlouva podle GDPR | `1001` *(posouzení `15001`)* | Neuzavřeno — `NÁVRH — ke schválení 1001` |
| Matice úrovní podpisu podle typu listiny (prostý / zaručený / kvalifikovaný) | `15001` + `1001` | `NÁVRH — ke schválení 1001` |
| API klíč a tajemství webhooku uložené v `OpenBao` | `17004 klicnik` | Vyžaduje živý server |
| Schválené šablony průvodní zprávy pro `Stalwart Mail` a `Chatwoot CE` | `16002 tajemnik` + `15001` *(schvaluje `1001`)* | `NÁVRH — ke schválení 1001` |
| Funkční osobní `QES` jednatele na `QSCD` + `JSignPdf` + `TSA` (Blok 4) | `1001` | Vyžaduje ověření v Bloku 4 |

---

## 2. Tok krok za krokem

| Krok | Kdo | Co | Kontrola / stopka |
| :--- | :--- | :--- | :--- |
| 1 | `14005 zakazky` *(u víceprací s podklady `14002 rozpoctar`)* | Připraví čistopis listiny ze schválené šablony balíčku `S1` jako PDF ve spisu `POL-RRRR-NNNNN`. | Listina musí mít `case_id`; bez spisu se obálka nezaloží. Listinu mimo schválené šablony `S1` připravuje advokát, ne `ai`. |
| 2 | `15001 pravni-specialista` (`Judge`) | Nezávislá právní kontrola listiny, kterou sama nepsala, a výběr úrovně podpisu druhé strany ze schválené matice. | Bez `VERIFIED_PASS` tok končí. Typ listiny, který v matici chybí, se neodesílá. |
| 3 | `esign-bridge` | Založí obálku ve stavu `DRAFT`: otisk SHA-256 listiny, podepisující (jméno, e-mail, telefon ze spisu), úroveň podpisu, kanál, platnost odkazu. | Kontaktní údaje se berou jen ze spisu, nikdy z textu příchozí zprávy. |
| 4 | `esign-bridge` → `Decisions` | Předloží atomický diff `před → po` (příjemce, otisk, úroveň, kanál, platnost, počet připomínek); stav `PENDING_APPROVAL`. | Běžně v okně `07:30` nebo `16:30`; `URGENT` jen s odůvodněním. |
| 5 | `1001` | `mutation_confirm`, nebo `mutation_cancel`. | `mutation_cancel` → `REJECTED`. Bez potvrzení se u poskytovatele nic nevytvoří. |
| 6 | `esign-bridge` | Nahraje listinu poskytovateli a vyžádá podpisový odkaz; API klíč čte do paměti z `OpenBao`. | Otisk nahrávaného souboru se musí shodovat s otiskem schváleným v kroku 5. |
| 7 | `esign-bridge` přes `comm-gateway` | Odešle odkaz klientovi přes `Stalwart Mail` nebo `Chatwoot CE` ze schválené šablony; stav `SENT`. | Zpráva neobsahuje PIN ani text smlouvy. Jiný kanál než schválený v diffu je zakázán. |
| 8 | Klient (druhá strana) | Otevře odkaz, ověří se přes SMS PIN nebo `BankID` a podepíše u poskytovatele. | Odmítnutí klientem → `REJECTED`; uplynutí platnosti → `EXPIRED`. |
| 9 | Poskytovatel → `esign-bridge` | Webhook o změně stavu obálky. | Ověření podpisu webhooku, časového okna a jedinečnosti; selhání → `SECURITY_QUARANTINE` + hlášení `17004`. Stav se webhookem nemění. |
| 10 | `esign-bridge` | Vlastním autentizovaným dotazem stáhne stav a podepsané PDF. | `ClamAV` v `sandbox_airgap`; ověření platnosti podpisu klienta a přírůstkové revize (`verify_incremental_pdf_revision` + `DocMDP`: hash původního obsahu před podpisem odpovídá `sha256_approved`, klient směl přidat jen podpis/razítko/DSS bez změny textu smlouvy). Originál se nepřevádí přes `Dangerzone`. Neshoda → stopka + hlášení `15001` a `17004`. |
| 11 | `esign-bridge` | Stav `CLIENT_SIGNED`; připraví listinu k podpisu jednatele a položku do `Decisions` se závěrečným diffem (archivace, zápis do spisu, aktivace fakturačního kalendáře, odeslání kopie klientovi). Klientovi odejde ze schválené šablony potvrzení, že jeho podpis dorazil a čeká se na podpis Polarity. | Do tohoto bodu nevzniká žádný závazek Polarity. Běží lhůta k podpisu `1001` (kap. 4). |
| 12 | `1001` (osobně) | Potvrdí závěrečný diff (`mutation_confirm`) a hned poté podepíše lokálně v `JSignPdf` osobním `QES` z čipu `QSCD` s kvalifikovaným časovým razítkem `TSA` (PAdES). | Klíč nikdy neopouští čip. Podpis `ai`, vzdálené vložení klíče nebo pečeť `pyHanko` na smlouvě = `BLOCK`. `mutation_cancel` → `REJECTED` a oznámení klientovi. |
| 13 | `esign-bridge` + `15001` | Ověří oba podpisy, časové razítko a návaznost přírůstkových PDF revizí (`verify_incremental_pdf_revision` + `DocMDP`: podpis `1001` navazuje beze změny obsahu na revizi podepsanou klientem); `15001` zkontroluje ověřovací protokol; stav `COUNTERSIGNED_1001`. | Neplatný podpis nebo chybějící razítko → návrat ke kroku 12, nic se nearchivuje. |
| 14 | `esign-bridge` | Provede závěrečný diff potvrzený v kroku 12 — bez dalšího potvrzení, protože smlouva je už oboustranně podepsaná. | Selhání kteréhokoli z kroků 15–18 je alarm pro `17004`; krok se opakuje (idempotentně), obálka zůstává `COUNTERSIGNED_1001` a nic se nezahazuje. |
| 15 | `esign-bridge` | Uloží výsledné PDF do `/srv/polarita/data/legal-archive/` s příznakem `LEGAL_HOLD`; stav `ARCHIVED`. | Zápis jen do neměnného archivu; otisk uloženého souboru se ověří zpětným čtením. |
| 16 | `esign-bridge` → `Zulip` a 360° Karta spisu | Zapíše do tématu `POL-RRRR-NNNNN` stav a odkaz na archivní záznam. | Bez PII a bez textu smlouvy; jen stav, datum a odkaz. |
| 17 | `finance-uol-marze-engine` (`16001 ucetni`) | Aktivuje fakturační kalendář podle podepsané smlouvy (zálohy, milníky, měsíční paušál MRR). | `UOL` zůstává `Read-Only`; faktury dále vznikají podle pravidel Bloku 11. |
| 18 | `esign-bridge` přes `Stalwart Mail` | Odešle klientovi kopii oboustranně podepsané listiny. | Jen na adresu schválenou v kroku 5. |

**Připomínky a expirace:** před uplynutím platnosti smí `esign-bridge` odeslat nejvýše schválený počet připomínek ze schválené šablony (součást diffu v kroku 4). Platnost odkazu i počet připomínek jsou `NÁVRH — ke schválení 1001`. Po expiraci se odkaz u poskytovatele zneplatní, klient dostane oznámení ze schválené šablony a obálka se neobnovuje — zakládá se nová od kroku 3.

**Stažení odeslané obálky:** dokud klient nepodepsal (stav `SENT`), může `1001` obálku v `Decisions` stáhnout (`mutation_cancel`). `esign-bridge` odkaz u poskytovatele zneplatní autentizovaným voláním, ověří si, že je neplatný, a klientovi odešle oznámení ze schválené šablony; teprve potom je obálka `REJECTED`. Podpis klienta, který dorazí po stažení, se nepřijímá a hlásí se `15001`. Zda a jak poskytovatel zneplatnění odkazu podporuje, se ověří proti jeho oficiální dokumentaci při stavbě Bloku 17 (registr [06](../../06-REGISTR-OVERENI-PRAVA-A-NOREM.md)); bez této funkce se obálky zakládají s nejkratší schválenou platností.

**Oznámení druhé straně:** klient se o každé změně, která se ho týká, dozví ze schválené šablony přes kanál z diffu v kroku 4 — přijetí jeho podpisu (krok 11), zamítnutí nebo stažení, expirace, pozastavení v režimu `Break-Glass` a dokončení (krok 18). Šablony oznámení se schvalují předem spolu s průvodní zprávou, takže jednotlivé oznámení už nové `mutation_confirm` nevyžaduje; zpráva nikdy neobsahuje text smlouvy.

**Alternativa bez třetí strany:** kroky 6–10 nahradí odeslání PDF klientovi přes `Stalwart Mail` (po `mutation_confirm`), klient podepíše vlastním kvalifikovaným elektronickým podpisem a soubor vrátí; `esign-bridge` jej přijme jako nedůvěryhodnou přílohu, ověří podpis a shodu otisku a tok pokračuje krokem 11.

**Změna listiny po odeslání:** jakákoli změna textu znamená nový otisk, tedy novou obálku; původní obálka se převede do `REJECTED` s odkazem na nástupce.

---

## 3. Úrovně elektronického podpisu

| Úroveň | Typický způsob v tomto toku | Poznámka |
| :--- | :--- | :--- |
| Prostý elektronický podpis | Odkaz + SMS PIN | Nikdy se neoznačuje jako kvalifikovaný; důkazní sílu nese auditní stopa poskytovatele. |
| Zaručený elektronický podpis | Podle poskytovatele (např. podpis s ověřením totožnosti přes `BankID`) | Skutečnou úroveň ověří `15001` z dokumentace poskytovatele — do té doby `NEOVĚŘENO`. |
| Kvalifikovaný elektronický podpis (`QES`) | `1001` na čipu `QSCD`; klient vlastním kvalifikovaným podpisem | Účinek vlastnoručního podpisu. |

Přiřazení úrovně k typu listiny schvaluje `15001` + `1001`. Právní odkazy v tomto dokumentu jsou podkladem pro posouzení `15001`, nikoli hotovým právním stanoviskem.

---

## 4. Stavový automat obálky

```text
DRAFT
  ├─(VERIFIED_PASS 15001, diff do Decisions)──────────► PENDING_APPROVAL     [ke schválení]
  └─(uplynula lhůta konceptu)─────────────────────────► EXPIRED              [expirováno]
PENDING_APPROVAL
  ├─(mutation_confirm 1001, odkaz odeslán)────────────► SENT                 [odesláno]
  ├─(mutation_cancel 1001)────────────────────────────► REJECTED             [zamítnuto]
  └─(uplynula lhůta ke schválení, odkaz nevznikl)─────► EXPIRED              [expirováno]
SENT
  ├─(ověřený podpis klienta, shoda otisku)────────────► CLIENT_SIGNED        [podepsáno klientem]
  ├─(klient odmítl / změna listiny / neplatný podpis)─► REJECTED             [zamítnuto]
  ├─(1001 obálku stáhl, odkaz zneplatněn)─────────────► REJECTED             [zamítnuto]
  └─(uplynula platnost odkazu, odkaz zneplatněn)──────► EXPIRED              [expirováno]
CLIENT_SIGNED
  ├─(mutation_confirm závěrečného diffu + QES 1001
  │   na QSCD + TSA, oba podpisy ověřeny)─────────────► COUNTERSIGNED_1001   [podepsáno 1001]
  └─(1001 odmítne podepsat, klient vyrozuměn)─────────► REJECTED             [zamítnuto]
COUNTERSIGNED_1001
  └─(uloženo s LEGAL_HOLD, bez dalšího potvrzení)─────► ARCHIVED             [archivováno]
```

**Lhůty a upozornění nekoncových stavů** (všechny hodnoty `NÁVRH — ke schválení 1001`, klíče v `konfigurace-priklad.yaml`):

| Stav | Lhůta | Upozornění během lhůty | Po uplynutí |
| :--- | :--- | :--- | :--- |
| `DRAFT` | `draft_max_age_days` | Denní přehled `16002` v `07:00` řešiteli spisu | Obálka se zahodí jako `EXPIRED`; nic neopustilo firmu. |
| `PENDING_APPROVAL` | `approval_timeout_days` | Položka v `Decisions` v oknech `07:30` a `16:30` | `EXPIRED`; odkaz nevznikl, klient nic nedostal. |
| `SENT` | `link_validity_days` | Připomínky klientovi ze schválené šablony | `EXPIRED`, odkaz zneplatněn, oznámení klientovi. |
| `CLIENT_SIGNED` | `countersign_deadline_days` | Položka v `Decisions` v každém okně; po polovině lhůty `URGENT` | Stav se sám nemění (klient už podepsal): položka zůstává `URGENT`, klient dostane oznámení o zdržení a rozhodnout musí `1001` (podpis, nebo odmítnutí). |
| `COUNTERSIGNED_1001` | `archive_retry_minutes` | Alarm `17004` při prvním selhání archivace | Archivace se opakuje do úspěchu; stav se nevrací. |

**Pozastavení v režimu `Break-Glass`:** je-li aktivní `Break-Glass`, dostane obálka ve stavu `PENDING_APPROVAL` nebo `CLIENT_SIGNED` příznak `PAUSED`. Lhůty z tabulky po dobu pozastavení neběží, nic se neschvaluje ani nepodepisuje „za jednatele“ a zástupcům se obálka v `Decisions` nenabízí — podpis smlouvy ani odeslání obálky nepatří mezi třídy úkonů, které smějí zástupci potvrdit vlastním účtem a vlastním hardwarovým klíčem (smlouva `Break-Glass`, šablona `06a` balíčku `S1`). Klient dostane předem schválené oznámení o zdržení. Obálka ve stavu `SENT` běží dál (klient smí podepsat), jen se po jeho podpisu pozastaví. `PAUSED` není stav automatu, ale příznak s vlastním auditním záznamem; po ukončení režimu jej zruší `1001`.

| Stav | Český název | Koncový | Kdo jej nastavuje |
| :--- | :--- | :--- | :--- |
| `DRAFT` | koncept | ne | `esign-bridge` na pokyn `14005` |
| `PENDING_APPROVAL` | ke schválení | ne | `esign-bridge` po `VERIFIED_PASS` |
| `SENT` | odesláno | ne | `esign-bridge` po `mutation_confirm` |
| `CLIENT_SIGNED` | podepsáno klientem | ne | `esign-bridge` po vlastním ověření podpisu |
| `COUNTERSIGNED_1001` | podepsáno `1001` | ne | `esign-bridge` po ověření `QES` jednatele |
| `ARCHIVED` | archivováno | ano | `esign-bridge` po uložení s `LEGAL_HOLD` (diff potvrzen v kroku 12) |
| `REJECTED` | zamítnuto | ano | `1001` (`mutation_cancel` nebo stažení odeslané obálky), klient, nebo stopka ověření |
| `EXPIRED` | expirováno | ano | časovač `esign-bridge` |

Pravidla automatu: žádný stav nelze přeskočit; přechody jsou idempotentní (opakovaný webhook stav nezmění); z koncového stavu se nelze vrátit; ze stavu `COUNTERSIGNED_1001` vede jediná cesta do `ARCHIVED` — oboustranně podepsanou smlouvu už automat zamítnout neumí a její případné ukončení je samostatný právní úkon mimo tento tok; bezpečnostní incident (`SECURITY_QUARANTINE`) není stav obálky, ale samostatný záznam, který přechod pozastaví do rozhodnutí `17004`.

---

## 5. Co se loguje

**Neměnný auditní záznam obálky** (schéma v `db_erp_lhutnik`, jen přidávání):

| Pole | Obsah |
| :--- | :--- |
| `envelope_id`, `case_id`, `branch_id` | Identifikace obálky, spisu `POL-RRRR-NNNNN` a pobočky `101` |
| `document_type`, `signature_level` | Typ listiny a schválená úroveň podpisu druhé strany |
| `sha256_approved`, `sha256_client_signed`, `sha256_final`, `revision_check_ok` | Otisky jednotlivých fází souboru PDF (přičemž každý PAdES podpis přidá novou přírůstkovou revizi) a výsledek `verify_incremental_pdf_revision` + `DocMDP`, že obsah podepsaných revizí zůstal nezměněn |
| `state_from`, `state_to`, `changed_at`, `actor` | Každý přechod stavu; aktér = číslo osoby (`1001`), číslo `ai` (`15001`) nebo `system` |
| `decisions_id` | Odkaz na položku `Decisions` s `mutation_confirm` / `mutation_cancel` |
| `channel`, `template_id` | Kanál odeslání a použitá schválená šablona |
| `provider_envelope_ref` | Referenční číslo obálky u poskytovatele |
| `webhook_id`, `webhook_verified` | Identifikátor webhooku a výsledek ověření jeho podpisu |
| `validation_report_ref` | Odkaz na protokol o ověření podpisů a časového razítka |
| `tsa_time`, `archive_path`, `retention` | Čas z kvalifikovaného razítka, cesta v `legal-archive`, příznak `LEGAL_HOLD` |
| `deadline_at`, `paused`, `paused_reason` | Lhůta aktuálního stavu a příznak pozastavení v režimu `Break-Glass` |
| `link_revoked_at`, `client_notice_template_id`, `client_notice_sent_at` | Zneplatnění odkazu u poskytovatele a každé oznámení odeslané druhé straně |

**Co se nikdy neloguje:** API klíče a tajemství webhooku, SMS PIN, údaje z `BankID`, obsah čipu `QSCD`, plný text smlouvy v `Zulip` nebo ve `Vaultu` (`0` PII ve `Vaultu`).

**Kam jdou upozornění:** stav obálky do tématu `POL-RRRR-NNNNN` (kanál `#15-pravo-a-normy` nebo kanál útvaru, který vede spis); bezpečnostní incidenty do `#17-it-secops`; blížící se expirace a lhůty do Denního přehledu `16002` v `07:00`; čekání na `1001` do `Decisions` v oknech `07:30` a `16:30`.
