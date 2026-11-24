-- =====================================================================================
-- rls-vzor.sql — Polarita Elektro Cloud · Blok 19 (S7) · Verze 3.9 (Polarita-3.9)
--
-- EN: This design pattern passed its assertions on disposable PostgreSQL 18.7.
-- CZ: Tento návrhový vzor prošel kontrolami na dočasné instanci PostgreSQL 18.7.
--
-- EN: How to try it: connect as an administrator to an EMPTY throw-away database
--     and run the whole file. Everything happens in one transaction that ends
--     with ROLLBACK, so no role, schema or row is left behind. A failed
--     assertion raises an exception "TEST n FAIL" and aborts the script.
-- CZ: Jak vzor vyzkoušet: připoj se jako administrátor k PRÁZDNÉ databázi určené
--     k zahození a spusť celý soubor. Vše běží v jedné transakci zakončené
--     ROLLBACK, takže po skriptu nezůstane žádná role, schéma ani řádek.
--     Nesplněná kontrola vyvolá výjimku "TEST n FAIL" a skript přeruší.
-- EN: Send the statements one by one (for example psql with the file as input), not as
--     one multi-statement string: TEST 14 relies on every statement having its own start
--     time, and it deliberately waits a few seconds.
-- CZ: Příkazy posílej jednotlivě (například psql se souborem na vstupu), ne jako jeden
--     řetězec s více příkazy: TEST 14 spoléhá na to, že každý příkaz má vlastní čas
--     začátku, a záměrně několik sekund čeká.
--
-- EN: Production layout (PRIMARY MODEL): one shared application schema where every
--     business table carries a compound key (tenant_id, id), ENABLE + FORCE ROW LEVEL
--     SECURITY and an AS RESTRICTIVE tenant guard policy created TO PUBLIC, so it binds
--     every current and future role and cannot be weakened by a permissive policy added
--     for another role. Per-tenant DEK keys live in OpenBao. Dedicated per-tenant schemas
--     remain an optional enterprise isolation mode only — NOT the default, so PgBouncer
--     pooling and schema migrations stay single-path.
-- CZ: Produkční uspořádání (PRIMÁRNÍ MODEL): jedno sdílené aplikační schéma, kde každá
--     doménová tabulka nese složený klíč (tenant_id, id), ENABLE + FORCE ROW LEVEL
--     SECURITY a omezující politiku AS RESTRICTIVE vytvořenou TO PUBLIC, takže váže
--     každou současnou i budoucí roli a nelze ji oslabit přidáním PERMISSIVE politiky
--     pro jinou roli. Vlastní šifrovací klíč tenanta je v OpenBao. Vyhrazené schéma pro
--     jediného tenanta je jen volitelný nadstandard, nikoli výchozí model (aby fungovalo
--     sdružování spojení PgBouncerem a jednotné migrace).
--
-- EN: Tenant context: the application role never states "I am tenant X". It presents an
--     opaque, short-lived session token issued by the authentication gateway after the
--     OIDC token was verified. The database resolves the token to a tenant itself.
-- CZ: Kontext tenanta: aplikační role nikdy netvrdí „jsem tenant X“. Předkládá neprůhledný
--     krátkodobý token relace, který po ověření tokenu OIDC vydala autentizační brána.
--     Na tenanta si token převádí databáze sama.
-- =====================================================================================

BEGIN;

-- -------------------------------------------------------------------------------------
-- 1. Roles / Role
-- -------------------------------------------------------------------------------------
-- EN: saas_owner       owns the objects and runs schema migrations; it cannot log in and,
--                      because of FORCE, it sees no business rows.
--     saas_app         the only role the application connects with.
--     saas_auth        the authentication gateway: after verifying the OIDC token it issues
--                      a session token row. It cannot read or write business tables.
--     saas_provisioner tenant onboarding / offboarding: the only role allowed to write the
--                      tenant registry and the tenant state. Offboarding = deactivation
--                      in tenant_stav; the role has no DELETE. It cannot read or write
--                      business tables.
--     None of the roles is a superuser and none has BYPASSRLS. Passwords / certificates
--     are provisioned from OpenBao, never written into SQL files.
-- CZ: saas_owner       vlastní objekty a spouští migrace schématu; nemůže se přihlásit a
--                      kvůli FORCE nevidí žádné doménové řádky.
--     saas_app         jediná role, kterou se připojuje aplikace.
--     saas_auth        autentizační brána: po ověření tokenu OIDC vydá řádek s tokenem
--                      relace. Doménové tabulky nečte ani do nich nezapisuje.
--     saas_provisioner zakládání a ukončování tenantů: jediná role, která smí zapisovat do
--                      registru tenantů a do stavu tenanta. Ukončení = deaktivace
--                      v tenant_stav; právo DELETE role nemá. Doménové tabulky nečte
--                      ani do nich nezapisuje.
--     Žádná z rolí není superuser a žádná nemá BYPASSRLS. Hesla / certifikáty se dodávají
--     z OpenBao, nikdy se nezapisují do SQL souborů.
CREATE ROLE saas_owner       NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE saas_app         LOGIN   NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE ROLE saas_auth        LOGIN   NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE ROLE saas_provisioner LOGIN   NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;

-- -------------------------------------------------------------------------------------
-- 2. Schema and tables / Schéma a tabulky
-- -------------------------------------------------------------------------------------
CREATE SCHEMA saas_vzor;
REVOKE ALL ON SCHEMA saas_vzor FROM PUBLIC;

-- EN: Tenant registry (one row per subscribing company). Written only by saas_provisioner.
-- CZ: Registr tenantů (jeden řádek na předplatitelskou firmu). Zapisuje jen saas_provisioner.
CREATE TABLE saas_vzor.tenant (
    tenant_id uuid PRIMARY KEY,
    nazev     text NOT NULL
);

-- EN: Tenant state — the part of the registry that decides about access. A tenant is
--     active only while a row with stav = 'ACTIVE' exists here; a missing row or
--     'DEACTIVATED' means no access (fail closed). Deactivation is one UPDATE by
--     saas_provisioner and must carry the time and the reference of the approved decision
--     (audit). The state is checked when a session token is issued (policy
--     session_role_guard) and every time a token is used (current_tenant_id), so tokens
--     issued earlier stop working with the first statement after the deactivation commits.
--     The state is kept apart from saas_vzor.tenant on purpose: the resolver must read it,
--     and the policy of the tenant table itself calls the resolver.
-- CZ: Stav tenanta — část registru, která rozhoduje o přístupu. Tenant je aktivní jen
--     tehdy, když zde existuje řádek se stav = 'ACTIVE'; chybějící řádek nebo
--     'DEACTIVATED' znamená žádný přístup (FAIL_CLOSED). Deaktivace je jeden UPDATE rolí
--     saas_provisioner a musí nést čas a odkaz na schválené rozhodnutí (audit). Stav se
--     ověřuje při vydání tokenu relace (politika session_role_guard) i při každém použití
--     tokenu (current_tenant_id), takže dříve vydané tokeny přestanou platit prvním
--     příkazem po potvrzení deaktivace. Stav je od saas_vzor.tenant oddělen záměrně:
--     resolver jej musí číst a politika samotné tabulky tenant resolver volá.
-- EN: Session generation: every session token carries the generation that was current
--     when it was issued, and it is valid only while the two are equal. Every change of
--     stav (deactivation AND reactivation) raises the generation in the same UPDATE
--     (trigger below), so all sessions issued before the change are revoked in the same
--     transaction and stay revoked after a reactivation — users must sign in again.
--     Raising the generation alone revokes all sessions of an active tenant.
-- CZ: Generace relací: každý token relace nese generaci platnou v okamžiku vydání a platí
--     jen, dokud se obě shodují. Každá změna stavu (deaktivace I reaktivace) zvýší generaci
--     v tomtéž UPDATE (trigger níže), takže všechny relace vydané před změnou jsou
--     revokovány ve stejné transakci a zůstávají revokované i po reaktivaci — uživatelé
--     se musí přihlásit znovu. Samotné zvýšení generace revokuje všechny relace aktivního
--     tenanta.
CREATE TABLE saas_vzor.tenant_stav (
    tenant_id       uuid PRIMARY KEY REFERENCES saas_vzor.tenant (tenant_id),
    stav            text NOT NULL DEFAULT 'ACTIVE'
                    CHECK (stav IN ('ACTIVE', 'DEACTIVATED')),
    generace_relaci integer NOT NULL DEFAULT 1 CHECK (generace_relaci >= 1),
    deaktivovano_at timestamptz,
    deaktivace_ref  text,
    CONSTRAINT tenant_stav_audit_ck CHECK (
        (stav = 'ACTIVE' AND deaktivovano_at IS NULL AND deaktivace_ref IS NULL)
        OR (stav = 'DEACTIVATED' AND deaktivovano_at IS NOT NULL AND deaktivace_ref IS NOT NULL)
    )
);

-- EN: Keeps the generation honest whatever the provisioning service sends: a change of
--     stav always moves it forward by at least one and it can never go back. Not
--     SECURITY DEFINER — it only touches the row being updated.
-- CZ: Drží generaci poctivou bez ohledu na to, co služba pro zakládání tenantů pošle:
--     změna stavu ji vždy posune aspoň o jednu vpřed a nikdy se nemůže vrátit. Není
--     SECURITY DEFINER — pracuje jen s právě měněným řádkem.
CREATE FUNCTION saas_vzor.tenant_stav_generace()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.stav IS DISTINCT FROM OLD.stav THEN
        NEW.generace_relaci := GREATEST(NEW.generace_relaci, OLD.generace_relaci + 1);
    ELSIF NEW.generace_relaci < OLD.generace_relaci THEN
        RAISE EXCEPTION 'generace_relaci cannot decrease'
              USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER tenant_stav_generace_trg
    BEFORE UPDATE ON saas_vzor.tenant_stav
    FOR EACH ROW
    EXECUTE FUNCTION saas_vzor.tenant_stav_generace();

-- EN: Session tokens issued by the authentication gateway. The token is a random UUID;
--     the application role has NO privilege on this table, so it can neither list tokens
--     of other tenants nor create one.
-- CZ: Tokeny relací vydané autentizační bránou. Token je náhodné UUID; aplikační role
--     nemá k této tabulce ŽÁDNÉ oprávnění, takže nemůže vypsat tokeny jiných tenantů
--     ani si token vytvořit.
CREATE TABLE saas_vzor.tenant_session (
    token      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL REFERENCES saas_vzor.tenant (tenant_id),
    -- EN: Session generation of the tenant at the moment of issue (see tenant_stav).
    -- CZ: Generace relací tenanta v okamžiku vydání (viz tenant_stav).
    generace   integer NOT NULL,
    expires_at timestamptz NOT NULL
);

-- EN: Resolves the tenant of the current statement from app.tenant_token. Missing, empty,
--     malformed, unknown or expired tokens and tokens of a tenant that is not ACTIVE return
--     NULL, so queries fail closed to 0 rows without leaking parse errors. SECURITY DEFINER
--     with a pinned search_path: the function reads tenant_session and tenant_stav on
--     behalf of the caller, who has no access to those tables. The legacy setting
--     app.tenant_id is deliberately ignored.
--     Expiry is compared with statement_timestamp(), NOT with now(): now() is the start of
--     the transaction, so a transaction left open would keep an expired token alive.
--     statement_timestamp() is the time the current command arrived from the client;
--     a single long statement, or a DO block / procedure with many inner statements, is
--     still judged by its start — therefore the length of statements and transactions of
--     saas_app is limited as well (section 4, known limit 8).
-- CZ: Určí tenanta aktuálního příkazu z app.tenant_token. Chybějící, prázdný, neplatný,
--     neznámý i prošlý token a token tenanta, který není ACTIVE, vrátí NULL, takže dotaz
--     selže bezpečně do 0 řádků bez úniku chyby převodu. SECURITY DEFINER s pevným
--     search_path: funkce čte tenant_session a tenant_stav za volajícího, který k těmto
--     tabulkám přístup nemá. Dřívější nastavení app.tenant_id se záměrně ignoruje.
--     Expirace se porovnává se statement_timestamp(), NE s now(): now() je začátek
--     transakce, takže otevřená transakce by držela prošlý token při životě.
--     statement_timestamp() je čas, kdy aktuální příkaz dorazil od klienta; jediný dlouhý
--     příkaz nebo blok DO / procedura s mnoha vnitřními příkazy se dál posuzuje podle
--     svého začátku — proto se omezuje i délka příkazů a transakcí role saas_app
--     (oddíl 4, známá mez 8).
CREATE FUNCTION saas_vzor.current_tenant_id()
RETURNS uuid
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    raw_token text;
    v_token   uuid;
    v_tenant  uuid;
BEGIN
    raw_token := NULLIF(current_setting('app.tenant_token', true), '');
    IF raw_token IS NULL THEN
        RETURN NULL;
    END IF;
    BEGIN
        v_token := raw_token::uuid;
    EXCEPTION
        WHEN invalid_text_representation THEN
            RETURN NULL;
    END;
    SELECT s.tenant_id
      INTO v_tenant
      FROM saas_vzor.tenant_session AS s
      JOIN saas_vzor.tenant_stav AS t ON t.tenant_id = s.tenant_id
     WHERE s.token = v_token
       AND s.expires_at > statement_timestamp()
       AND t.stav = 'ACTIVE'
       AND s.generace = t.generace_relaci;
    RETURN v_tenant;
END;
$$;
REVOKE ALL ON FUNCTION saas_vzor.current_tenant_id() FROM PUBLIC;

-- EN: Used when a token is ISSUED: returns the current session generation of a tenant
--     with an ACTIVE state row, otherwise NULL. The gateway writes the value into the new
--     token and the session-token policy compares it again, so a token cannot be issued
--     for a tenant that is not ACTIVE nor with a stale generation. SECURITY DEFINER with
--     a pinned search_path, because the authentication gateway has no access to tenant_stav.
-- CZ: Používá se při VYDÁNÍ tokenu: vrátí aktuální generaci relací tenanta s řádkem stavu
--     ACTIVE, jinak NULL. Brána hodnotu zapíše do nového tokenu a politika tokenů relací
--     ji porovná znovu, takže token nelze vydat tenantovi, který není ACTIVE, ani se
--     starou generací. SECURITY DEFINER s pevným search_path, protože autentizační brána
--     nemá k tenant_stav přístup.
CREATE FUNCTION saas_vzor.tenant_session_generation(p_tenant_id uuid)
RETURNS integer
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_generace integer;
BEGIN
    SELECT t.generace_relaci
      INTO v_generace
      FROM saas_vzor.tenant_stav AS t
     WHERE t.tenant_id = p_tenant_id
       AND t.stav = 'ACTIVE';
    RETURN v_generace;
END;
$$;
REVOKE ALL ON FUNCTION saas_vzor.tenant_session_generation(uuid) FROM PUBLIC;

-- EN: Sample business table (simplified "building" from the Digital Building Book).
--     Uses a compound UUID primary key (tenant_id, objekt_id) to avoid global sequence
--     leakage across tenants; tenant_id defaults from current_tenant_id() of the transaction.
-- CZ: Vzorová doménová tabulka (zjednodušený „objekt“ z Digitální knihy objektu).
--     Používá složený klíč UUID (tenant_id, objekt_id) bez sdíleného sekvenčního
--     čítače napříč tenanty; tenant_id se doplní z current_tenant_id() transakce.
CREATE TABLE saas_vzor.objekt (
    objekt_id  uuid NOT NULL DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL
               DEFAULT saas_vzor.current_tenant_id()
               REFERENCES saas_vzor.tenant (tenant_id),
    nazev      text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, objekt_id),
    -- EN: Unique keys always include tenant_id, otherwise a constraint error
    --     would reveal that another tenant uses the same value.
    -- CZ: Unikátní klíče vždy obsahují tenant_id, jinak by chyba omezení
    --     prozradila, že stejnou hodnotu používá jiný tenant.
    CONSTRAINT objekt_tenant_nazev_uq UNIQUE (tenant_id, nazev)
);

-- EN: Clean Room aggregate view runs with caller privileges (security_invoker = true),
--     so FORCE + RESTRICTIVE RLS applies automatically inside the view as well.
-- CZ: Clean Room pohled běží s oprávněními volajícího (security_invoker = true),
--     takže FORCE + RESTRICTIVE RLS platí i při čtení pohledu.
CREATE VIEW saas_vzor.v_objekt_clean_room
WITH (security_invoker = true) AS
SELECT tenant_id, count(*) AS pocet_objektu
  FROM saas_vzor.objekt
 GROUP BY tenant_id;

-- -------------------------------------------------------------------------------------
-- 3. Row-Level Security
-- -------------------------------------------------------------------------------------
-- EN: ENABLE turns RLS on; FORCE makes it apply to the table owner as well.
--     Without FORCE the owner (saas_owner) would silently see every tenant.
-- CZ: ENABLE zapíná RLS; FORCE jej vynutí i pro vlastníka tabulky.
--     Bez FORCE by vlastník (saas_owner) tiše viděl všechny tenanty.
ALTER TABLE saas_vzor.tenant         ENABLE ROW LEVEL SECURITY;
ALTER TABLE saas_vzor.tenant         FORCE  ROW LEVEL SECURITY;
ALTER TABLE saas_vzor.tenant_stav    ENABLE ROW LEVEL SECURITY;
ALTER TABLE saas_vzor.tenant_stav    FORCE  ROW LEVEL SECURITY;
ALTER TABLE saas_vzor.tenant_session ENABLE ROW LEVEL SECURITY;
ALTER TABLE saas_vzor.tenant_session FORCE  ROW LEVEL SECURITY;
ALTER TABLE saas_vzor.objekt         ENABLE ROW LEVEL SECURITY;
ALTER TABLE saas_vzor.objekt         FORCE  ROW LEVEL SECURITY;

-- EN: Business table. The tenant guard is AS RESTRICTIVE and TO PUBLIC: PostgreSQL requires
--     ALL restrictive policies that apply to the current role to pass, and a policy TO PUBLIC
--     applies to every role. A permissive policy added later for any role therefore cannot
--     open another tenant. The scalar sub-select makes the planner evaluate the function
--     once per statement instead of once per row.
-- CZ: Doménová tabulka. Pojistka tenanta je AS RESTRICTIVE a TO PUBLIC: PostgreSQL vyžaduje
--     splnění VŠECH omezujících politik platných pro aktuální roli a politika TO PUBLIC
--     platí pro každou roli. Později přidaná PERMISSIVE politika pro kteroukoli roli tedy
--     nemůže otevřít cizího tenanta. Skalární poddotaz zajistí vyhodnocení funkce jednou
--     na příkaz, ne jednou na řádek.
CREATE POLICY tenant_guard ON saas_vzor.objekt
    AS RESTRICTIVE
    FOR ALL
    TO PUBLIC
    USING      (tenant_id = (SELECT saas_vzor.current_tenant_id()))
    WITH CHECK (tenant_id = (SELECT saas_vzor.current_tenant_id()));

CREATE POLICY objekt_app_access ON saas_vzor.objekt
    AS PERMISSIVE
    FOR ALL
    TO saas_app
    USING      (true)
    WITH CHECK (true);

-- EN: Tenant registry. Everyone sees at most the own tenant row; the single named exception
--     is saas_provisioner, and only that role may write. The exception is part of the
--     restrictive policy itself, so it is visible in one place and checked by TEST 12.
-- CZ: Registr tenantů. Každý vidí nejvýše řádek vlastního tenanta; jedinou jmenovitou
--     výjimkou je saas_provisioner a zapisovat smí jen tato role. Výjimka je součástí
--     samotné omezující politiky, takže je vidět na jednom místě a hlídá ji TEST 12.
CREATE POLICY tenant_self_guard ON saas_vzor.tenant
    AS RESTRICTIVE
    FOR ALL
    TO PUBLIC
    USING      (tenant_id = (SELECT saas_vzor.current_tenant_id())
                OR current_user = 'saas_provisioner')
    WITH CHECK (current_user = 'saas_provisioner');

CREATE POLICY tenant_self_read ON saas_vzor.tenant
    AS PERMISSIVE
    FOR SELECT
    TO saas_app
    USING (true);

CREATE POLICY tenant_provisioning ON saas_vzor.tenant
    AS PERMISSIVE
    FOR ALL
    TO saas_provisioner
    USING      (true)
    WITH CHECK (true);

-- EN: Tenant state. Only saas_provisioner writes; the owner may read, because the two
--     SECURITY DEFINER functions run as the owner. The policies do not call
--     current_tenant_id(), so the resolver can read this table without recursion.
-- CZ: Stav tenanta. Zapisuje jen saas_provisioner; číst smí vlastník, protože obě funkce
--     SECURITY DEFINER běží jako vlastník. Politiky nevolají current_tenant_id(), takže
--     resolver může tabulku číst bez rekurze.
CREATE POLICY stav_role_guard ON saas_vzor.tenant_stav
    AS RESTRICTIVE
    FOR ALL
    TO PUBLIC
    USING      (current_user IN ('saas_provisioner', 'saas_owner'))
    WITH CHECK (current_user = 'saas_provisioner');

CREATE POLICY stav_provisioning ON saas_vzor.tenant_stav
    AS PERMISSIVE
    FOR ALL
    TO saas_provisioner
    USING      (true)
    WITH CHECK (true);

CREATE POLICY stav_owner_lookup ON saas_vzor.tenant_stav
    AS PERMISSIVE
    FOR SELECT
    TO saas_owner
    USING (true);

-- EN: Session tokens. Only the authentication gateway writes, and only for a tenant that
--     is ACTIVE at that moment; the owner may read, because current_tenant_id()
--     (SECURITY DEFINER) runs as the owner. Nobody else passes.
-- CZ: Tokeny relací. Zapisuje jen autentizační brána, a to jen pro tenanta, který je
--     v tom okamžiku ACTIVE; číst smí vlastník, protože current_tenant_id()
--     (SECURITY DEFINER) běží jako vlastník. Nikdo jiný neprojde.
CREATE POLICY session_role_guard ON saas_vzor.tenant_session
    AS RESTRICTIVE
    FOR ALL
    TO PUBLIC
    USING      (current_user IN ('saas_auth', 'saas_owner'))
    WITH CHECK (current_user = 'saas_auth'
                AND generace = saas_vzor.tenant_session_generation(tenant_id));

CREATE POLICY session_auth_access ON saas_vzor.tenant_session
    AS PERMISSIVE
    FOR ALL
    TO saas_auth
    USING      (true)
    WITH CHECK (true);

CREATE POLICY session_owner_lookup ON saas_vzor.tenant_session
    AS PERMISSIVE
    FOR SELECT
    TO saas_owner
    USING (true);

-- -------------------------------------------------------------------------------------
-- 4. Privileges and ownership / Oprávnění a vlastnictví
-- -------------------------------------------------------------------------------------
-- EN: Least privilege. Revoke PUBLIC defaults; no TRUNCATE for anyone; the application
--     role has no registry writes and no access to session tokens.
-- CZ: Nejmenší oprávnění. Zrušit výchozí PUBLIC práva; TRUNCATE nemá nikdo; aplikační
--     role nezapisuje do registru a nemá přístup k tokenům relací.
REVOKE ALL ON ALL TABLES IN SCHEMA saas_vzor FROM PUBLIC;

GRANT USAGE ON SCHEMA saas_vzor TO saas_app, saas_auth, saas_provisioner;
GRANT EXECUTE ON FUNCTION saas_vzor.current_tenant_id() TO saas_app, saas_provisioner;
GRANT EXECUTE ON FUNCTION saas_vzor.tenant_session_generation(uuid) TO saas_auth;

GRANT SELECT ON saas_vzor.tenant TO saas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON saas_vzor.objekt TO saas_app;
GRANT SELECT ON saas_vzor.v_objekt_clean_room TO saas_app;

GRANT SELECT, INSERT, UPDATE ON saas_vzor.tenant TO saas_provisioner;
GRANT SELECT, INSERT, UPDATE ON saas_vzor.tenant_stav TO saas_provisioner;
GRANT SELECT, INSERT, DELETE ON saas_vzor.tenant_session TO saas_auth;

-- EN: Expiry is judged per statement, so statements and transactions of the application
--     role must be short. The values are a PROPOSAL to be set well below the token
--     lifetime; they take effect at the next login of the role. Whether the deployed
--     version also offers a limit on the whole transaction must be verified against the
--     official PostgreSQL documentation when Block 19 is built.
-- CZ: Expirace se posuzuje po příkazech, takže příkazy i transakce aplikační role musí být
--     krátké. Hodnoty jsou NÁVRH — ke schválení 1001 a nastavují se výrazně pod životnost
--     tokenu; projeví se při dalším přihlášení role. Zda nasazená verze nabízí i limit na
--     celou transakci, je nutné ověřit proti oficiální dokumentaci PostgreSQL při stavbě
--     Bloku 19.
ALTER ROLE saas_app SET statement_timeout = '30s';
ALTER ROLE saas_app SET idle_in_transaction_session_timeout = '60s';

ALTER SCHEMA   saas_vzor OWNER TO saas_owner;
ALTER FUNCTION saas_vzor.current_tenant_id() OWNER TO saas_owner;
ALTER FUNCTION saas_vzor.tenant_session_generation(uuid) OWNER TO saas_owner;
ALTER FUNCTION saas_vzor.tenant_stav_generace() OWNER TO saas_owner;
ALTER TABLE    saas_vzor.tenant OWNER TO saas_owner;
ALTER TABLE    saas_vzor.tenant_stav OWNER TO saas_owner;
ALTER TABLE    saas_vzor.tenant_session OWNER TO saas_owner;
ALTER TABLE    saas_vzor.objekt OWNER TO saas_owner;
ALTER VIEW     saas_vzor.v_objekt_clean_room OWNER TO saas_owner;

-- -------------------------------------------------------------------------------------
-- 5. Seed data written THROUGH the policies / Vzorová data zapsaná PŘES politiky
-- -------------------------------------------------------------------------------------
-- EN: From here on the script acts as the non-privileged roles. A superuser always
--     bypasses RLS, so tests run as an administrator would prove nothing.
-- CZ: Odtud skript vystupuje jako neprivilegované role. Superuser RLS vždy obchází,
--     takže testy spuštěné administrátorem by nic nedokázaly.

-- EN: 5a. Onboarding: synthetic tenants A and B are created by saas_provisioner, each
--     with its state row (ACTIVE). Without the state row no token can be issued or used.
-- CZ: 5a. Onboarding: syntetické tenanty A a B zakládá saas_provisioner, každého i s řádkem
--     stavu (ACTIVE). Bez řádku stavu nelze token vydat ani použít.
SET LOCAL ROLE saas_provisioner;
INSERT INTO saas_vzor.tenant (tenant_id, nazev) VALUES
    ('11111111-1111-4111-8111-111111111111', 'Vzorová elektro firma A (syntetická)'),
    ('22222222-2222-4222-8222-222222222222', 'Vzorová elektro firma B (syntetická)');
INSERT INTO saas_vzor.tenant_stav (tenant_id) VALUES
    ('11111111-1111-4111-8111-111111111111'),
    ('22222222-2222-4222-8222-222222222222');

-- EN: 5b. Sign-in: the authentication gateway issues session tokens. Fixed values are used
--     here only to keep the pattern readable; in production the token is gen_random_uuid(),
--     lives for minutes and is handed to the application over the authenticated channel.
--     The third row is an already expired token of tenant A (used by TEST 7).
-- CZ: 5b. Přihlášení: autentizační brána vydává tokeny relací. Pevné hodnoty jsou zde jen
--     kvůli čitelnosti vzoru; v provozu je token gen_random_uuid(), žije minuty a aplikaci
--     se předává ověřeným kanálem. Třetí řádek je již prošlý token tenanta A (pro TEST 7).
SET LOCAL ROLE saas_auth;
INSERT INTO saas_vzor.tenant_session (token, tenant_id, generace, expires_at) VALUES
    ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '11111111-1111-4111-8111-111111111111',
     saas_vzor.tenant_session_generation('11111111-1111-4111-8111-111111111111'), now() + interval '15 minutes'),
    ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '22222222-2222-4222-8222-222222222222',
     saas_vzor.tenant_session_generation('22222222-2222-4222-8222-222222222222'), now() + interval '15 minutes'),
    ('cccccccc-cccc-4ccc-8ccc-cccccccccccc', '11111111-1111-4111-8111-111111111111',
     saas_vzor.tenant_session_generation('11111111-1111-4111-8111-111111111111'), now() - interval '1 minute');

-- EN: 5c. The application sets the token per transaction with set_config(..., true)
--     (= SET LOCAL) — never per session, because pooled connections are shared.
-- CZ: 5c. Aplikace nastavuje token pro každou transakci přes set_config(..., true)
--     (= SET LOCAL) — nikdy na celou relaci, protože spojení z poolu jsou sdílená.
SET LOCAL ROLE saas_app;

SELECT set_config('app.tenant_token', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
INSERT INTO saas_vzor.objekt (nazev) VALUES
    ('Bytový dům Vzorová 1 (tenant A)'),
    ('Výrobní hala Vzorová 2 (tenant A)');

SELECT set_config('app.tenant_token', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', true);
INSERT INTO saas_vzor.objekt (nazev) VALUES
    ('Bytový dům Příkladná 3 (tenant B)');

-- -------------------------------------------------------------------------------------
-- 6. Tests: tenant A must not see or touch data of tenant B
--    Testy: tenant A nesmí vidět ani měnit data tenanta B
-- -------------------------------------------------------------------------------------

-- EN: TEST 1 — tenant A sees exactly its own 2 rows and no foreign row.
-- CZ: TEST 1 — tenant A vidí právě své 2 řádky a žádný cizí.
DO $$
DECLARE
    n_all     bigint;
    n_foreign bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
    SELECT count(*),
           count(*) FILTER (WHERE tenant_id <> '11111111-1111-4111-8111-111111111111'::uuid)
      INTO n_all, n_foreign
      FROM saas_vzor.objekt;
    IF n_all <> 2 OR n_foreign <> 0 THEN
        RAISE EXCEPTION 'TEST 1 FAIL: tenant A sees % rows, % foreign', n_all, n_foreign;
    END IF;
    RAISE NOTICE 'TEST 1 PASS: tenant A sees only its own 2 rows / vidi jen sve 2 radky';
END
$$;

-- EN: TEST 2 — an explicit filter on tenant B returns nothing for tenant A.
-- CZ: TEST 2 — výslovný filtr na tenanta B nevrátí tenantovi A nic.
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
    SELECT count(*) INTO n
      FROM saas_vzor.objekt
     WHERE tenant_id = '22222222-2222-4222-8222-222222222222'::uuid;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 2 FAIL: tenant A reads % rows of tenant B', n;
    END IF;
    SELECT count(*) INTO n FROM saas_vzor.tenant;
    IF n <> 1 THEN
        RAISE EXCEPTION 'TEST 2 FAIL: tenant A sees % registry rows instead of 1', n;
    END IF;
    RAISE NOTICE 'TEST 2 PASS: tenant A cannot read tenant B / necte data tenanta B';
END
$$;

-- EN: TEST 3 — UPDATE and DELETE aimed at tenant B affect 0 rows.
-- CZ: TEST 3 — UPDATE a DELETE mířící na tenanta B nezasáhnou žádný řádek.
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
    UPDATE saas_vzor.objekt
       SET nazev = 'prepsano tenantem A'
     WHERE tenant_id = '22222222-2222-4222-8222-222222222222'::uuid;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 3 FAIL: tenant A updated % rows of tenant B', n;
    END IF;
    DELETE FROM saas_vzor.objekt
     WHERE tenant_id = '22222222-2222-4222-8222-222222222222'::uuid;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 3 FAIL: tenant A deleted % rows of tenant B', n;
    END IF;
    RAISE NOTICE 'TEST 3 PASS: tenant A cannot update or delete tenant B / nezmeni ani nesmaze';
END
$$;

-- EN: TEST 4 — tenant A cannot insert a row for tenant B (WITH CHECK).
-- CZ: TEST 4 — tenant A nemůže vložit řádek za tenanta B (WITH CHECK).
DO $$
BEGIN
    PERFORM set_config('app.tenant_token', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
    BEGIN
        INSERT INTO saas_vzor.objekt (tenant_id, nazev)
        VALUES ('22222222-2222-4222-8222-222222222222', 'podvrzeny objekt');
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'TEST 4 PASS: insert for tenant B rejected / vlozeni za tenanta B odmitnuto';
            RETURN;
    END;
    RAISE EXCEPTION 'TEST 4 FAIL: tenant A inserted a row for tenant B';
END
$$;

-- EN: TEST 5 — tenant A cannot move its own row to tenant B (WITH CHECK on UPDATE).
-- CZ: TEST 5 — tenant A nemůže přesunout svůj řádek k tenantovi B (WITH CHECK u UPDATE).
DO $$
BEGIN
    PERFORM set_config('app.tenant_token', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
    BEGIN
        UPDATE saas_vzor.objekt
           SET tenant_id = '22222222-2222-4222-8222-222222222222';
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'TEST 5 PASS: moving a row to tenant B rejected / presun k tenantovi B odmitnut';
            RETURN;
    END;
    RAISE EXCEPTION 'TEST 5 FAIL: tenant A moved a row to tenant B';
END
$$;

-- EN: TEST 6 — tenant B still has exactly its 1 untouched row.
-- CZ: TEST 6 — tenant B má stále právě svůj 1 nedotčený řádek.
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', true);
    SELECT count(*) INTO n
      FROM saas_vzor.objekt
     WHERE nazev = 'Bytový dům Příkladná 3 (tenant B)';
    IF n <> 1 THEN
        RAISE EXCEPTION 'TEST 6 FAIL: tenant B row is missing or changed (found %)', n;
    END IF;
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 1 THEN
        RAISE EXCEPTION 'TEST 6 FAIL: tenant B sees % rows instead of 1', n;
    END IF;
    RAISE NOTICE 'TEST 6 PASS: tenant B data intact / data tenanta B nedotcena';
END
$$;

-- EN: TEST 7 — no token, malformed token, unknown token and expired token:
--     0 rows visible, no insert (FAIL_CLOSED).
-- CZ: TEST 7 — žádný token, neplatný token, neznámý token a prošlý token:
--     0 řádků, zápis zakázán (FAIL_CLOSED).
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', '', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 7 FAIL: % rows visible without a token', n;
    END IF;
    PERFORM set_config('app.tenant_token', 'not-a-uuid', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 7 FAIL: % rows visible with a malformed token', n;
    END IF;
    PERFORM set_config('app.tenant_token', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 7 FAIL: % rows visible with an unknown token', n;
    END IF;
    PERFORM set_config('app.tenant_token', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 7 FAIL: % rows visible with an expired token', n;
    END IF;
    BEGIN
        INSERT INTO saas_vzor.objekt (nazev) VALUES ('objekt bez tenanta');
    EXCEPTION
        WHEN insufficient_privilege OR not_null_violation THEN
            RAISE NOTICE 'TEST 7 PASS: missing / invalid / expired token = 0 rows / neplatny token zadna data';
            RETURN;
    END;
    RAISE EXCEPTION 'TEST 7 FAIL: insert without a valid token succeeded';
END
$$;

-- EN: TEST 8 — Clean Room security_invoker view & least-privilege blocks on tenant registry / TRUNCATE.
-- CZ: TEST 8 — Clean Room pohled (security_invoker) a zákaz zápisu do registru tenantů / TRUNCATE.
DO $$
DECLARE
    cnt bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
    SELECT pocet_objektu INTO cnt FROM saas_vzor.v_objekt_clean_room;
    IF cnt <> 2 THEN
        RAISE EXCEPTION 'TEST 8 FAIL: Clean Room view for tenant A returned % instead of 2', cnt;
    END IF;
    SELECT count(*) INTO cnt FROM saas_vzor.v_objekt_clean_room;
    IF cnt <> 1 THEN
        RAISE EXCEPTION 'TEST 8 FAIL: Clean Room view leaked foreign rows (count = %)', cnt;
    END IF;
    BEGIN
        INSERT INTO saas_vzor.tenant (tenant_id, nazev) VALUES (gen_random_uuid(), 'Podvrzený tenant');
        RAISE EXCEPTION 'TEST 8 FAIL: saas_app inserted into tenant registry';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        TRUNCATE saas_vzor.objekt;
        RAISE EXCEPTION 'TEST 8 FAIL: saas_app could TRUNCATE objekt';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    RAISE NOTICE 'TEST 8 PASS: Clean Room view isolated and registry/TRUNCATE blocked';
END
$$;

-- EN: TEST 9 — the application role cannot appoint itself to another tenant. Stating the
--     tenant directly (legacy app.tenant_id, or tenant B's id used as a token) yields
--     0 rows, and saas_app can neither read nor create session tokens.
-- CZ: TEST 9 — aplikační role se nemůže sama prohlásit za jiného tenanta. Přímé uvedení
--     tenanta (dřívější app.tenant_id, nebo id tenanta B použité jako token) dá 0 řádků
--     a saas_app nemůže tokeny relací číst ani vytvářet.
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', '', true);
    PERFORM set_config('app.tenant_id', '22222222-2222-4222-8222-222222222222', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 9 FAIL: app.tenant_id alone opened % rows', n;
    END IF;
    PERFORM set_config('app.tenant_token', '22222222-2222-4222-8222-222222222222', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 9 FAIL: tenant id used as a token opened % rows', n;
    END IF;
    BEGIN
        SELECT count(*) INTO n FROM saas_vzor.tenant_session;
        RAISE EXCEPTION 'TEST 9 FAIL: saas_app can read session tokens';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        INSERT INTO saas_vzor.tenant_session (tenant_id, generace, expires_at)
        VALUES ('22222222-2222-4222-8222-222222222222', 1, now() + interval '15 minutes');
        RAISE EXCEPTION 'TEST 9 FAIL: saas_app created a session token';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    RAISE NOTICE 'TEST 9 PASS: tenant cannot be self-declared / tenanta nelze prohlasit sam';
END
$$;

-- EN: TEST 10 — FORCE ROW LEVEL SECURITY: even the table owner sees no business row,
--     because no permissive policy is granted to it (default deny).
-- CZ: TEST 10 — FORCE ROW LEVEL SECURITY: ani vlastník tabulky nevidí žádný doménový řádek,
--     protože pro něj neexistuje žádná PERMISSIVE politika (výchozí zákaz).
SET LOCAL ROLE saas_owner;
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 10 FAIL: table owner sees % rows despite FORCE RLS', n;
    END IF;
    RAISE NOTICE 'TEST 10 PASS: owner is subject to RLS / vlastnik podleha RLS';
END
$$;

-- EN: TEST 11 — provisioning and authentication roles: saas_provisioner can add and rename
--     a tenant but has no access to business data; saas_auth cannot write the registry.
-- CZ: TEST 11 — role pro zakládání a pro autentizaci: saas_provisioner umí přidat a
--     přejmenovat tenanta, ale nemá přístup k doménovým datům; saas_auth do registru nezapíše.
SET LOCAL ROLE saas_provisioner;
DO $$
DECLARE
    n bigint;
BEGIN
    INSERT INTO saas_vzor.tenant (tenant_id, nazev)
    VALUES ('33333333-3333-4333-8333-333333333333', 'Vzorová elektro firma C (syntetická)');
    UPDATE saas_vzor.tenant
       SET nazev = 'Vzorová elektro firma C (syntetická, přejmenovaná)'
     WHERE tenant_id = '33333333-3333-4333-8333-333333333333'::uuid;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n <> 1 THEN
        RAISE EXCEPTION 'TEST 11 FAIL: provisioner updated % registry rows instead of 1', n;
    END IF;
    SELECT count(*) INTO n FROM saas_vzor.tenant;
    IF n <> 3 THEN
        RAISE EXCEPTION 'TEST 11 FAIL: provisioner sees % registry rows instead of 3', n;
    END IF;
    INSERT INTO saas_vzor.tenant_stav (tenant_id)
    VALUES ('33333333-3333-4333-8333-333333333333');
    BEGIN
        SELECT count(*) INTO n FROM saas_vzor.objekt;
        RAISE EXCEPTION 'TEST 11 FAIL: provisioner can read business data';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    RAISE NOTICE 'TEST 11a PASS: provisioner writes registry only / zapisuje jen registr';
END
$$;

SET LOCAL ROLE saas_auth;
DO $$
BEGIN
    BEGIN
        INSERT INTO saas_vzor.tenant (tenant_id, nazev) VALUES (gen_random_uuid(), 'Podvrzený tenant');
        RAISE EXCEPTION 'TEST 11 FAIL: saas_auth inserted into tenant registry';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM 1 FROM saas_vzor.objekt;
        RAISE EXCEPTION 'TEST 11 FAIL: saas_auth can read business data';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    RAISE NOTICE 'TEST 11b PASS: auth gateway issues tokens only / vydava jen tokeny';
END
$$;

-- EN: TEST 12 — catalog check: RLS enabled and forced on every regular/partitioned table,
--     every such table has a RESTRICTIVE policy TO PUBLIC, 0 materialized views, no
--     SUPERUSER / BYPASSRLS among the four roles, and every SECURITY DEFINER function
--     has search_path pinned to exactly "pg_catalog, pg_temp". The check reads the VALUE
--     of search_path in pg_proc.proconfig; a function that sets only some other parameter
--     does not pass (TEST 13 proves it). The stored text form of the value must be
--     verified against the official documentation of the deployed PostgreSQL version when
--     Block 19 is built; a different trusted path must be allowed here explicitly.
-- CZ: TEST 12 — kontrola katalogu: RLS zapnuté a vynucené na každé běžné i dělené tabulce,
--     každá taková tabulka má omezující politiku TO PUBLIC, 0 materializovaných pohledů,
--     žádná ze čtyř rolí není SUPERUSER / BYPASSRLS a každá funkce SECURITY DEFINER
--     má search_path připnutý přesně na „pg_catalog, pg_temp“. Kontrola čte HODNOTU
--     search_path v pg_proc.proconfig; funkce, která nastavuje jen jiný parametr,
--     neprojde (dokazuje to TEST 13). Uložený textový tvar hodnoty je nutné ověřit proti
--     oficiální dokumentaci nasazené verze PostgreSQL při stavbě Bloku 19; jinou
--     důvěryhodnou cestu je nutné zde povolit výslovně.
RESET ROLE;
DO $$
DECLARE
    n bigint;
BEGIN
    SELECT count(*) INTO n
      FROM pg_class c
      JOIN pg_namespace s ON s.oid = c.relnamespace
     WHERE s.nspname = 'saas_vzor'
       AND c.relkind IN ('r', 'p')
       AND NOT (c.relrowsecurity AND c.relforcerowsecurity);
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 12 FAIL: % tables without enabled and forced RLS', n;
    END IF;
    SELECT count(*) INTO n
      FROM pg_class c
      JOIN pg_namespace s ON s.oid = c.relnamespace
     WHERE s.nspname = 'saas_vzor'
       AND c.relkind IN ('r', 'p')
       AND NOT EXISTS (
               SELECT 1
                 FROM pg_policy p
                WHERE p.polrelid = c.oid
                  AND NOT p.polpermissive
                  AND p.polcmd = '*'
                  AND '0'::oid = ANY (p.polroles)
           );
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 12 FAIL: % tables without a RESTRICTIVE FOR ALL policy TO PUBLIC', n;
    END IF;
    SELECT count(*) INTO n
      FROM pg_class c
      JOIN pg_namespace s ON s.oid = c.relnamespace
     WHERE s.nspname = 'saas_vzor'
       AND c.relkind = 'm';
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 12 FAIL: % unguarded materialized views in tenant schema', n;
    END IF;
    SELECT count(*) INTO n
      FROM pg_roles
     WHERE rolname IN ('saas_owner', 'saas_app', 'saas_auth', 'saas_provisioner')
       AND (rolsuper OR rolbypassrls);
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 12 FAIL: % roles are superuser or have BYPASSRLS', n;
    END IF;
    SELECT count(*) INTO n
      FROM pg_proc f
      JOIN pg_namespace s ON s.oid = f.pronamespace
     WHERE s.nspname = 'saas_vzor'
       AND f.prosecdef
       AND NOT EXISTS (
               SELECT 1
                 FROM unnest(f.proconfig) AS c(setting)
                WHERE split_part(c.setting, '=', 1) = 'search_path'
                  AND replace(replace(substr(c.setting, length('search_path=') + 1), ' ', ''), '"', '')
                      = 'pg_catalog,pg_temp'
           );
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 12 FAIL: % SECURITY DEFINER functions without search_path = pg_catalog, pg_temp', n;
    END IF;
    RAISE NOTICE 'TEST 12 PASS: RLS forced, restrictive guard TO PUBLIC everywhere, 0 matviews, no BYPASSRLS, search_path pinned';
END
$$;

-- EN: TEST 13 — negative test of the search_path check from TEST 12. Three deliberately
--     wrong SECURITY DEFINER functions are created: one without any setting, one that sets
--     only another parameter (the earlier "proconfig IS NULL" check let this one through)
--     and one with search_path set to an untrusted path. The check must report all three;
--     after they are dropped it must report none.
-- CZ: TEST 13 — záporný test kontroly search_path z TESTU 12. Vzniknou tři záměrně chybné
--     funkce SECURITY DEFINER: jedna bez jakéhokoli nastavení, jedna, která nastavuje jen
--     jiný parametr (tu dřívější kontrola „proconfig IS NULL“ propustila), a jedna se
--     search_path nastaveným na nedůvěryhodnou cestu. Kontrola musí ohlásit všechny tři;
--     po jejich odstranění nesmí ohlásit žádnou.
CREATE FUNCTION saas_vzor.zkouska_bez_nastaveni() RETURNS integer
    LANGUAGE sql SECURITY DEFINER
    AS 'SELECT 1';
CREATE FUNCTION saas_vzor.zkouska_jiny_parametr() RETURNS integer
    LANGUAGE sql SECURITY DEFINER
    SET lock_timeout = '5s'
    AS 'SELECT 1';
CREATE FUNCTION saas_vzor.zkouska_spatna_cesta() RETURNS integer
    LANGUAGE sql SECURITY DEFINER
    SET search_path = public, pg_catalog
    AS 'SELECT 1';
DO $$
DECLARE
    n bigint;
BEGIN
    SELECT count(*) INTO n
      FROM pg_proc f
      JOIN pg_namespace s ON s.oid = f.pronamespace
     WHERE s.nspname = 'saas_vzor'
       AND f.prosecdef
       AND NOT EXISTS (
               SELECT 1
                 FROM unnest(f.proconfig) AS c(setting)
                WHERE split_part(c.setting, '=', 1) = 'search_path'
                  AND replace(replace(substr(c.setting, length('search_path=') + 1), ' ', ''), '"', '')
                      = 'pg_catalog,pg_temp'
           );
    IF n <> 3 THEN
        RAISE EXCEPTION 'TEST 13 FAIL: search_path check reported % of 3 wrong functions', n;
    END IF;
END
$$;
DROP FUNCTION saas_vzor.zkouska_bez_nastaveni();
DROP FUNCTION saas_vzor.zkouska_jiny_parametr();
DROP FUNCTION saas_vzor.zkouska_spatna_cesta();
DO $$
DECLARE
    n bigint;
BEGIN
    SELECT count(*) INTO n
      FROM pg_proc f
      JOIN pg_namespace s ON s.oid = f.pronamespace
     WHERE s.nspname = 'saas_vzor'
       AND f.prosecdef
       AND NOT EXISTS (
               SELECT 1
                 FROM unnest(f.proconfig) AS c(setting)
                WHERE split_part(c.setting, '=', 1) = 'search_path'
                  AND replace(replace(substr(c.setting, length('search_path=') + 1), ' ', ''), '"', '')
                      = 'pg_catalog,pg_temp'
           );
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 13 FAIL: % functions still reported after the wrong ones were dropped', n;
    END IF;
    RAISE NOTICE 'TEST 13 PASS: search_path check rejects missing / other / untrusted settings';
END
$$;

-- EN: TEST 14 — a token that expires while the transaction is still open. The whole file
--     is ONE transaction, so now() stays at its start and is earlier than expires_at of
--     the token issued below for the rest of the script: a check against now() would
--     accept the token forever. The resolver compares with statement_timestamp(), so the
--     first statement sent after the expiry sees 0 rows and cannot insert.
--     The script waits here on purpose (pg_sleep).
-- CZ: TEST 14 — token, který vyprší, zatímco je transakce stále otevřená. Celý soubor je
--     JEDNA transakce, takže now() zůstává na jejím začátku a po zbytek skriptu je dřívější
--     než expires_at tokenu vydaného níže: kontrola vůči now() by token přijímala napořád.
--     Resolver porovnává se statement_timestamp(), takže první příkaz odeslaný po expiraci
--     vidí 0 řádků a nic nevloží. Skript zde záměrně čeká (pg_sleep).
SET LOCAL ROLE saas_auth;
INSERT INTO saas_vzor.tenant_session (token, tenant_id, generace, expires_at) VALUES
    ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', '11111111-1111-4111-8111-111111111111',
     saas_vzor.tenant_session_generation('11111111-1111-4111-8111-111111111111'),
     clock_timestamp() + interval '5 seconds');

SET LOCAL ROLE saas_app;
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 2 THEN
        RAISE EXCEPTION 'TEST 14 FAIL: short-lived token shows % rows instead of 2 before expiry', n;
    END IF;
END
$$;

SELECT pg_sleep(6);

DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 14 FAIL: % rows visible after the token expired inside the open transaction', n;
    END IF;
    BEGIN
        INSERT INTO saas_vzor.objekt (nazev) VALUES ('objekt po expiraci tokenu');
    EXCEPTION
        WHEN insufficient_privilege OR not_null_violation THEN
            RAISE NOTICE 'TEST 14 PASS: token expired inside an open transaction = 0 rows / token vyprsel v otevrene transakci';
            RETURN;
    END;
    RAISE EXCEPTION 'TEST 14 FAIL: insert with a token expired inside the open transaction succeeded';
END
$$;

-- EN: TEST 15 — tenant deactivation (offboarding) and reactivation. saas_provisioner
--     deactivates tenant B with one audited UPDATE. The token of tenant B issued earlier
--     is still in tenant_session and has not expired, yet it opens nothing; the gateway
--     cannot issue a new token for tenant B; tenant A is not affected; saas_app cannot
--     touch the state; a deactivation without time and decision reference is rejected.
--     Then tenant B is reactivated: the OLD token stays dead (its generation is stale),
--     a token with the stale generation cannot be issued, the generation cannot be turned
--     back, and only a token issued after the reactivation opens the data of tenant B.
-- CZ: TEST 15 — deaktivace tenanta (ukončení) a reaktivace. saas_provisioner deaktivuje
--     tenanta B jedním auditovaným UPDATE. Dříve vydaný token tenanta B je stále
--     v tenant_session a nevypršel, přesto neotevře nic; brána nový token pro tenanta B
--     nevydá; tenanta A se změna netýká; saas_app na stav nedosáhne; deaktivace bez času
--     a odkazu na rozhodnutí je odmítnuta. Poté je tenant B reaktivován: STARÝ token
--     zůstává mrtvý (má starou generaci), token se starou generací nelze vydat, generaci
--     nelze vrátit zpět a data tenanta B otevře až token vydaný po reaktivaci.
SET LOCAL ROLE saas_app;
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 1 THEN
        RAISE EXCEPTION 'TEST 15 FAIL: tenant B sees % rows instead of 1 before deactivation', n;
    END IF;
    BEGIN
        UPDATE saas_vzor.tenant_stav SET stav = 'ACTIVE';
        RAISE EXCEPTION 'TEST 15 FAIL: saas_app can write the tenant state';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END
$$;

SET LOCAL ROLE saas_provisioner;
DO $$
DECLARE
    n bigint;
BEGIN
    BEGIN
        UPDATE saas_vzor.tenant_stav
           SET stav = 'DEACTIVATED'
         WHERE tenant_id = '22222222-2222-4222-8222-222222222222'::uuid;
        RAISE EXCEPTION 'TEST 15 FAIL: deactivation without time and decision reference accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    UPDATE saas_vzor.tenant_stav
       SET stav = 'DEACTIVATED',
           deaktivovano_at = clock_timestamp(),
           deaktivace_ref = 'Decisions: ukončení smlouvy tenanta B (syntetický odkaz)'
     WHERE tenant_id = '22222222-2222-4222-8222-222222222222'::uuid;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n <> 1 THEN
        RAISE EXCEPTION 'TEST 15 FAIL: provisioner deactivated % tenants instead of 1', n;
    END IF;
END
$$;

SET LOCAL ROLE saas_auth;
DO $$
BEGIN
    BEGIN
        INSERT INTO saas_vzor.tenant_session (tenant_id, generace, expires_at)
        VALUES ('22222222-2222-4222-8222-222222222222', 2, clock_timestamp() + interval '15 minutes');
        RAISE EXCEPTION 'TEST 15 FAIL: token issued for a deactivated tenant';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    INSERT INTO saas_vzor.tenant_session (token, tenant_id, generace, expires_at)
    VALUES ('ffffffff-ffff-4fff-8fff-ffffffffffff', '11111111-1111-4111-8111-111111111111',
            saas_vzor.tenant_session_generation('11111111-1111-4111-8111-111111111111'),
            clock_timestamp() + interval '15 minutes');
END
$$;

SET LOCAL ROLE saas_app;
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 15 FAIL: deactivated tenant B still sees % rows', n;
    END IF;
    SELECT count(*) INTO n FROM saas_vzor.tenant;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 15 FAIL: deactivated tenant B still sees % registry rows', n;
    END IF;
    BEGIN
        INSERT INTO saas_vzor.objekt (nazev) VALUES ('objekt deaktivovaneho tenanta');
        RAISE EXCEPTION 'TEST 15 FAIL: deactivated tenant B inserted a row';
    EXCEPTION WHEN insufficient_privilege OR not_null_violation THEN NULL;
    END;
    PERFORM set_config('app.tenant_token', 'ffffffff-ffff-4fff-8fff-ffffffffffff', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 2 THEN
        RAISE EXCEPTION 'TEST 15 FAIL: active tenant A sees % rows instead of 2', n;
    END IF;
END
$$;

-- EN: Reactivation of tenant B (generation 1 -> 2 at deactivation, 2 -> 3 now).
-- CZ: Reaktivace tenanta B (generace 1 -> 2 při deaktivaci, 2 -> 3 nyní).
SET LOCAL ROLE saas_provisioner;
DO $$
DECLARE
    g integer;
BEGIN
    UPDATE saas_vzor.tenant_stav
       SET stav = 'ACTIVE',
           deaktivovano_at = NULL,
           deaktivace_ref = NULL
     WHERE tenant_id = '22222222-2222-4222-8222-222222222222'::uuid
 RETURNING generace_relaci INTO g;
    IF g IS DISTINCT FROM 3 THEN
        RAISE EXCEPTION 'TEST 15 FAIL: session generation is % instead of 3 after reactivation', g;
    END IF;
    BEGIN
        UPDATE saas_vzor.tenant_stav
           SET generace_relaci = 1
         WHERE tenant_id = '22222222-2222-4222-8222-222222222222'::uuid;
        RAISE EXCEPTION 'TEST 15 FAIL: session generation was turned back';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END
$$;

SET LOCAL ROLE saas_app;
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 15 FAIL: old token of tenant B revived by reactivation (% rows)', n;
    END IF;
END
$$;

SET LOCAL ROLE saas_auth;
DO $$
BEGIN
    BEGIN
        INSERT INTO saas_vzor.tenant_session (tenant_id, generace, expires_at)
        VALUES ('22222222-2222-4222-8222-222222222222', 1, clock_timestamp() + interval '15 minutes');
        RAISE EXCEPTION 'TEST 15 FAIL: token with a stale generation issued';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    INSERT INTO saas_vzor.tenant_session (token, tenant_id, generace, expires_at)
    VALUES ('99999999-9999-4999-8999-999999999999', '22222222-2222-4222-8222-222222222222',
            saas_vzor.tenant_session_generation('22222222-2222-4222-8222-222222222222'),
            clock_timestamp() + interval '15 minutes');
END
$$;

SET LOCAL ROLE saas_app;
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_token', '99999999-9999-4999-8999-999999999999', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 1 THEN
        RAISE EXCEPTION 'TEST 15 FAIL: reactivated tenant B sees % rows instead of 1 with a new token', n;
    END IF;
    RAISE NOTICE 'TEST 15 PASS: deactivation revokes sessions, reactivation needs a new sign-in / deaktivace revokuje relace';
END
$$;
RESET ROLE;

-- -------------------------------------------------------------------------------------
-- 7. Clean-up / Úklid
-- -------------------------------------------------------------------------------------
-- EN: The pattern leaves nothing behind. In a real migration the DDL from
--     sections 1–4 is generated by metadata-schema-kernel and committed; the
--     tests from section 6 run in Gitea Actions before every release.
--     Known limits to cover elsewhere:
--     (1) superusers and BYPASSRLS roles always bypass RLS;
--     (2) foreign-key and unique checks are not filtered by RLS;
--     (3) backups (pg_dump) need a dedicated, audited procedure;
--     (4) the token only moves the trust boundary: whoever holds a valid token of a tenant
--         acts as that tenant until it expires, so tokens must be short-lived, bound to one
--         signed-in user, deleted at sign-out and never logged; code running as saas_app
--         with an SQL injection flaw can still misuse the token of ITS OWN request, it just
--         cannot reach another tenant;
--     (5) a compromised authentication gateway (saas_auth) can issue a token for any tenant
--         and a compromised saas_provisioner can alter the registry — both run as separate
--         services with their own credentials and audit trail;
--     (6) data migrations that must touch rows of all tenants cannot run as saas_owner
--         (FORCE): they run per tenant through a dedicated, audited migration procedure;
--     (7) repeat these tests against the generated schema before deployment;
--     (8) token expiry is judged at the start of each statement: one long statement, or
--         a DO block / procedure with many inner statements, runs to its end with the token
--         it started with, and a REPEATABLE READ or SERIALIZABLE transaction does not see
--         a deactivation committed after its snapshot — the application role therefore
--         works in READ COMMITTED, in short transactions, with statement and idle limits
--         well below the token lifetime;
--     (9) deactivation closes access and revokes all sessions issued so far (session
--         generation); a later reactivation does not revive them. It does not delete the
--         tenant's rows, keys or backups, and the revoked token rows stay until the gateway
--         cleans them up; erasure after the end of
--         a contract and the full history of state changes (who, when, why) belong to
--         a separate audited procedure and to the append-only log of the provisioning
--         service;
--     (10) this file runs in ONE transaction and switches roles with SET LOCAL ROLE, so it
--         proves nothing about a real login of saas_app nor about a pooled connection
--         reused after COMMIT or ROLLBACK — that is the subject of the separate script
--         rls-pool-test.sql.
-- CZ: Vzor po sobě nic nezanechá. Ve skutečné migraci generuje DDL z oddílů 1–4
--     modul metadata-schema-kernel a potvrzuje se; testy z oddílu 6 běží
--     v Gitea Actions před každým vydáním.
--     Známé meze, které je nutné ošetřit jinde:
--     (1) superuser a role s BYPASSRLS RLS vždy obcházejí;
--     (2) kontroly cizích klíčů a unikátnosti RLS nefiltruje;
--     (3) zálohy (pg_dump) potřebují vyhrazený auditovaný postup;
--     (4) token jen posouvá hranici důvěry: kdo drží platný token tenanta, jedná do jeho
--         vypršení jako tento tenant, proto musí být tokeny krátkodobé, vázané na jednoho
--         přihlášeného uživatele, mazané při odhlášení a nikdy logované; kód běžící jako
--         saas_app s chybou typu SQL injection může dál zneužít token SVÉHO požadavku,
--         jen se nedostane k jinému tenantovi;
--     (5) kompromitovaná autentizační brána (saas_auth) může vydat token pro libovolného
--         tenanta a kompromitovaný saas_provisioner může měnit registr — obě běží jako
--         oddělené služby s vlastními přihlašovacími údaji a auditní stopou;
--     (6) datové migrace, které musí sáhnout na řádky všech tenantů, nemohou běžet jako
--         saas_owner (FORCE): běží po tenantech vyhrazeným auditovaným migračním postupem;
--     (7) před nasazením zopakuj kontroly nad vygenerovaným schématem;
--     (8) expirace tokenu se posuzuje na začátku každého příkazu: jeden dlouhý příkaz nebo
--         blok DO / procedura s mnoha vnitřními příkazy doběhne s tokenem, se kterým začal,
--         a transakce REPEATABLE READ nebo SERIALIZABLE nevidí deaktivaci potvrzenou po
--         svém snímku — aplikační role proto pracuje v READ COMMITTED, v krátkých
--         transakcích a s limity příkazu a nečinnosti výrazně pod životností tokenu;
--     (9) deaktivace uzavírá přístup a revokuje všechny dosud vydané relace (generace
--         relací); pozdější reaktivace je neobnoví. Nemaže řádky, klíče ani zálohy tenanta
--         a revokované řádky tokenů zůstávají, dokud je brána neuklidí; výmaz po skončení smlouvy a úplná historie změn
--         stavu (kdo, kdy, proč) patří do samostatného auditovaného postupu a do neměnného
--         deníku služby pro zakládání tenantů;
--     (10) tento soubor běží v JEDNÉ transakci a role přepíná přes SET LOCAL ROLE, takže
--         nic nedokládá o skutečném přihlášení role saas_app ani o spojení z poolu znovu
--         použitém po COMMIT nebo ROLLBACK — to je předmětem samostatného skriptu
--         rls-pool-test.sql.
ROLLBACK;
