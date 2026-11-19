# Podpisový workflow — dvoustranný elektronický podpis smluv (`esign-bridge`) · Blok 17 · Verze 2.7

Tento dokument popisuje krok za krokem tok dvoustranného podpisu Smlouvy o dílo, Změnového listu víceprací a servisní smlouvy `Elektro Správa SVJ a Firem` (MRR). Doplňuje řídicí dokument [README.md](README.md) (pravidla 1–10). Jde o návrh: konektor `esign-bridge` není naprogramován ani nasazen a smlouva s poskytovatelem podpisu není uzavřena.

**Tři pevné zásady celého toku:**

1. `ai` připravuje jen koncept (`DRAFT`); ven z firmy jde listina až po `mutation_confirm` jednatele `1001`.
2. Za Polaritu podepisuje vždy člověk `1001` osobním `QES` na čipu `QSCD`; nikdy `ai`, nikdy serverová pečeť `pyHanko`.
3. Vše, co přijde od poskytovatele nebo od klienta, je nedůvěryhodný vstup (`<untrusted_inbound_comm role="external_data">`), dokud to `esign-bridge` sám neověří.

---

## 1. Předpoklady před prvním použitím

| Předpoklad | Kdo | Stav ve Verzi 2.7 |
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
| 1 | `15001 pravni-specialista` + `14005 zakazky` *(u víceprací `14002 rozpoctar`)* | Připraví čistopis listiny jako PDF ve spisu `POL-RRRR-NNNNN`. | Listina musí mít `case_id`; bez spisu se obálka nezaloží. |
| 2 | `15001 pravni-specialista` (`Judge`) | Právní kontrola listiny a výběr úrovně podpisu druhé strany ze schválené matice. | Bez `VERIFIED_PASS` tok končí. Typ listiny, který v matici chybí, se neodesílá. |
| 3 | `esign-bridge` | Založí obálku ve stavu `DRAFT`: otisk SHA-256 listiny, podepisující (jméno, e-mail, telefon ze spisu), úroveň podpisu, kanál, platnost odkazu. | Kontaktní údaje se berou jen ze spisu, nikdy z textu příchozí zprávy. |
| 4 | `esign-bridge` → `Decisions` | Předloží atomický diff `před → po` (příjemce, otisk, úroveň, kanál, platnost, počet připomínek); stav `PENDING_APPROVAL`. | Běžně v okně `07:30` nebo `16:30`; `URGENT` jen s odůvodněním. |
| 5 | `1001` | `mutation_confirm`, nebo `mutation_cancel`. | `mutation_cancel` → `REJECTED`. Bez potvrzení se u poskytovatele nic nevytvoří. |
| 6 | `esign-bridge` | Nahraje listinu poskytovateli a vyžádá podpisový odkaz; API klíč čte do paměti z `OpenBao`. | Otisk nahrávaného souboru se musí shodovat s otiskem schváleným v kroku 5. |
| 7 | `esign-bridge` přes `comm-gateway` | Odešle odkaz klientovi přes `Stalwart Mail` nebo `Chatwoot CE` ze schválené šablony; stav `SENT`. | Zpráva neobsahuje PIN ani text smlouvy. Jiný kanál než schválený v diffu je zakázán. |
| 8 | Klient (druhá strana) | Otevře odkaz, ověří se přes SMS PIN nebo `BankID` a podepíše u poskytovatele. | Odmítnutí klientem → `REJECTED`; uplynutí platnosti → `EXPIRED`. |
| 9 | Poskytovatel → `esign-bridge` | Webhook o změně stavu obálky. | Ověření podpisu webhooku, časového okna a jedinečnosti; selhání → `SECURITY_QUARANTINE` + hlášení `17004`. Stav se webhookem nemění. |
| 10 | `esign-bridge` | Vlastním autentizovaným dotazem stáhne stav a podepsané PDF. | `ClamAV` v `sandbox_airgap`; ověření platnosti podpisu klienta; obsah musí odpovídat schválenému otisku. Originál se nepřevádí přes `Dangerzone`. Neshoda → stopka + hlášení `15001` a `17004`. |
| 11 | `esign-bridge` | Stav `CLIENT_SIGNED`; připraví listinu k podpisu jednatele a položku do `Decisions`. | Do tohoto bodu nevzniká žádný závazek Polarity. |
| 12 | `1001` (osobně) | Podepíše lokálně v `JSignPdf` osobním `QES` z čipu `QSCD` s kvalifikovaným časovým razítkem `TSA` (PAdES). | Klíč nikdy neopouští čip. Podpis `ai`, vzdálené vložení klíče nebo pečeť `pyHanko` na smlouvě = `BLOCK`. |
| 13 | `esign-bridge` + `15001` | Ověří oba podpisy, časové razítko a návaznost otisků; `15001` zkontroluje ověřovací protokol; stav `COUNTERSIGNED_1001`. | Neplatný podpis nebo chybějící razítko → návrat ke kroku 12, nic se nearchivuje. |
| 14 | `1001` | Potvrdí závěrečný diff (`mutation_confirm`): archivace, zápis do spisu, aktivace fakturačního kalendáře, odeslání kopie klientovi. | Bez potvrzení se fakturační kalendář neaktivuje. |
| 15 | `esign-bridge` | Uloží výsledné PDF do `/srv/polarita/data/legal-archive/` s příznakem `LEGAL_HOLD`; stav `ARCHIVED`. | Zápis jen do neměnného archivu; otisk uloženého souboru se ověří zpětným čtením. |
| 16 | `esign-bridge` → `Zulip` a 360° Karta spisu | Zapíše do tématu `POL-RRRR-NNNNN` stav a odkaz na archivní záznam. | Bez PII a bez textu smlouvy; jen stav, datum a odkaz. |
| 17 | `finance-uol-marze-engine` (`16001 ucetni`) | Aktivuje fakturační kalendář podle podepsané smlouvy (zálohy, milníky, měsíční paušál MRR). | `UOL` zůstává `Read-Only`; faktury dále vznikají podle pravidel Bloku 11. |
| 18 | `esign-bridge` přes `Stalwart Mail` | Odešle klientovi kopii oboustranně podepsané listiny. | Jen na adresu schválenou v kroku 5. |

**Připomínky a expirace:** před uplynutím platnosti smí `esign-bridge` odeslat nejvýše schválený počet připomínek ze schválené šablony (součást diffu v kroku 4). Platnost odkazu i počet připomínek jsou `NÁVRH — ke schválení 1001`. Po expiraci se obálka neobnovuje — zakládá se nová od kroku 3.

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
  └─(VERIFIED_PASS 15001, diff do Decisions)──────────► PENDING_APPROVAL     [ke schválení]
PENDING_APPROVAL
  ├─(mutation_confirm 1001, odkaz odeslán)────────────► SENT                 [odesláno]
  └─(mutation_cancel 1001)────────────────────────────► REJECTED             [zamítnuto]
SENT
  ├─(ověřený podpis klienta, shoda otisku)────────────► CLIENT_SIGNED        [podepsáno klientem]
  ├─(klient odmítl / změna listiny / neplatný podpis)─► REJECTED             [zamítnuto]
  └─(uplynula platnost odkazu)────────────────────────► EXPIRED              [expirováno]
CLIENT_SIGNED
  ├─(QES 1001 na QSCD + TSA, oba podpisy ověřeny)─────► COUNTERSIGNED_1001   [podepsáno 1001]
  └─(1001 odmítne podepsat)───────────────────────────► REJECTED             [zamítnuto]
COUNTERSIGNED_1001
  └─(mutation_confirm 1001, uloženo s LEGAL_HOLD)─────► ARCHIVED             [archivováno]
```

| Stav | Český název | Koncový | Kdo jej nastavuje |
| :--- | :--- | :--- | :--- |
| `DRAFT` | koncept | ne | `esign-bridge` na pokyn `15001` / `14005` |
| `PENDING_APPROVAL` | ke schválení | ne | `esign-bridge` po `VERIFIED_PASS` |
| `SENT` | odesláno | ne | `esign-bridge` po `mutation_confirm` |
| `CLIENT_SIGNED` | podepsáno klientem | ne | `esign-bridge` po vlastním ověření podpisu |
| `COUNTERSIGNED_1001` | podepsáno `1001` | ne | `esign-bridge` po ověření `QES` jednatele |
| `ARCHIVED` | archivováno | ano | `esign-bridge` po závěrečném `mutation_confirm` |
| `REJECTED` | zamítnuto | ano | `1001` (`mutation_cancel`), klient, nebo stopka ověření |
| `EXPIRED` | expirováno | ano | časovač `esign-bridge` |

Pravidla automatu: žádný stav nelze přeskočit; přechody jsou idempotentní (opakovaný webhook stav nezmění); z koncového stavu se nelze vrátit; bezpečnostní incident (`SECURITY_QUARANTINE`) není stav obálky, ale samostatný záznam, který přechod pozastaví do rozhodnutí `17004`.

---

## 5. Co se loguje

**Neměnný auditní záznam obálky** (schéma v `db_erp_lhutnik`, jen přidávání):

| Pole | Obsah |
| :--- | :--- |
| `envelope_id`, `case_id`, `branch_id` | Identifikace obálky, spisu `POL-RRRR-NNNNN` a pobočky `101` |
| `document_type`, `signature_level` | Typ listiny a schválená úroveň podpisu druhé strany |
| `sha256_approved`, `sha256_client_signed`, `sha256_final` | Otisky listiny ve třech bodech toku |
| `state_from`, `state_to`, `changed_at`, `actor` | Každý přechod stavu; aktér = číslo osoby (`1001`), číslo `ai` (`15001`) nebo `system` |
| `decisions_id` | Odkaz na položku `Decisions` s `mutation_confirm` / `mutation_cancel` |
| `channel`, `template_id` | Kanál odeslání a použitá schválená šablona |
| `provider_envelope_ref` | Referenční číslo obálky u poskytovatele |
| `webhook_id`, `webhook_verified` | Identifikátor webhooku a výsledek ověření jeho podpisu |
| `validation_report_ref` | Odkaz na protokol o ověření podpisů a časového razítka |
| `tsa_time`, `archive_path`, `retention` | Čas z kvalifikovaného razítka, cesta v `legal-archive`, příznak `LEGAL_HOLD` |

**Co se nikdy neloguje:** API klíče a tajemství webhooku, SMS PIN, údaje z `BankID`, obsah čipu `QSCD`, plný text smlouvy v `Zulip` nebo ve `Vaultu` (`0` PII ve `Vaultu`).

**Kam jdou upozornění:** stav obálky do tématu `POL-RRRR-NNNNN` (kanál `#15-pravo-a-normy` nebo kanál útvaru, který vede spis); bezpečnostní incidenty do `#17-it-secops`; blížící se expirace do Denního přehledu `16002` v `07:00`.
