-- =====================================================================================
-- rls-vzor.sql — Polarita Elektro Cloud · Blok 19 (S7) · Verze 3.0 (Polarita-3.0)
--
-- EN: PATTERN ONLY — NOT EXECUTED. This script is a design pattern for tenant
--     isolation in PostgreSQL. It has NOT been run against any live or test
--     database (the SaaS cluster does not exist; Block 19 is gated by the
--     Go / No-Go gate). Review and run it first in a disposable database.
-- CZ: POUZE VZOR — NEBYL SPUŠTĚN. Tento skript je návrhový vzor izolace tenantů
--     v PostgreSQL. NEBYL spuštěn proti žádné živé ani zkušební databázi (SaaS
--     klastr neexistuje; Blok 19 je podmíněn bránou Go / No-Go). Před použitím
--     jej zkontroluj a poprvé spusť v databázi určené k zahození.
--
-- EN: How to try it: connect as an administrator to an EMPTY throw-away database
--     and run the whole file. Everything happens in one transaction that ends
--     with ROLLBACK, so no role, schema or row is left behind. A failed
--     assertion raises an exception "TEST n FAIL" and aborts the script.
-- CZ: Jak vzor vyzkoušet: připoj se jako administrátor k PRÁZDNÉ databázi určené
--     k zahození a spusť celý soubor. Vše běží v jedné transakci zakončené
--     ROLLBACK, takže po skriptu nezůstane žádná role, schéma ani řádek.
--     Nesplněná kontrola vyvolá výjimku "TEST n FAIL" a skript přeruší.
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
--                      tenant registry. It cannot read or write business tables.
--     None of the roles is a superuser and none has BYPASSRLS. Passwords / certificates
--     are provisioned from OpenBao, never written into SQL files.
-- CZ: saas_owner       vlastní objekty a spouští migrace schématu; nemůže se přihlásit a
--                      kvůli FORCE nevidí žádné doménové řádky.
--     saas_app         jediná role, kterou se připojuje aplikace.
--     saas_auth        autentizační brána: po ověření tokenu OIDC vydá řádek s tokenem
--                      relace. Doménové tabulky nečte ani do nich nezapisuje.
--     saas_provisioner zakládání a ukončování tenantů: jediná role, která smí zapisovat do
--                      registru tenantů. Doménové tabulky nečte ani do nich nezapisuje.
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

-- EN: Session tokens issued by the authentication gateway. The token is a random UUID;
--     the application role has NO privilege on this table, so it can neither list tokens
--     of other tenants nor create one.
-- CZ: Tokeny relací vydané autentizační bránou. Token je náhodné UUID; aplikační role
--     nemá k této tabulce ŽÁDNÉ oprávnění, takže nemůže vypsat tokeny jiných tenantů
--     ani si token vytvořit.
CREATE TABLE saas_vzor.tenant_session (
    token      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL REFERENCES saas_vzor.tenant (tenant_id),
    expires_at timestamptz NOT NULL
);

-- EN: Resolves the tenant of the current transaction from app.tenant_token. Missing, empty,
--     malformed, unknown or expired tokens return NULL, so queries fail closed to 0 rows
--     without leaking parse errors. SECURITY DEFINER with a pinned search_path: the function
--     reads tenant_session on behalf of the caller, who has no access to that table.
--     The legacy setting app.tenant_id is deliberately ignored.
-- CZ: Určí tenanta aktuální transakce z app.tenant_token. Chybějící, prázdný, neplatný,
--     neznámý i prošlý token vrátí NULL, takže dotaz selže bezpečně do 0 řádků bez úniku
--     chyby převodu. SECURITY DEFINER s pevným search_path: funkce čte tenant_session za
--     volajícího, který k tabulce přístup nemá. Dřívější nastavení app.tenant_id se
--     záměrně ignoruje.
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
     WHERE s.token = v_token
       AND s.expires_at > now();
    RETURN v_tenant;
END;
$$;
REVOKE ALL ON FUNCTION saas_vzor.current_tenant_id() FROM PUBLIC;

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

-- EN: Session tokens. Only the authentication gateway writes; the owner may read, because
--     current_tenant_id() (SECURITY DEFINER) runs as the owner. Nobody else passes.
-- CZ: Tokeny relací. Zapisuje jen autentizační brána; číst smí vlastník, protože
--     current_tenant_id() (SECURITY DEFINER) běží jako vlastník. Nikdo jiný neprojde.
CREATE POLICY session_role_guard ON saas_vzor.tenant_session
    AS RESTRICTIVE
    FOR ALL
    TO PUBLIC
    USING      (current_user IN ('saas_auth', 'saas_owner'))
    WITH CHECK (current_user = 'saas_auth');

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

GRANT SELECT ON saas_vzor.tenant TO saas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON saas_vzor.objekt TO saas_app;
GRANT SELECT ON saas_vzor.v_objekt_clean_room TO saas_app;

GRANT SELECT, INSERT, UPDATE ON saas_vzor.tenant TO saas_provisioner;
GRANT SELECT, INSERT, DELETE ON saas_vzor.tenant_session TO saas_auth;

ALTER SCHEMA   saas_vzor OWNER TO saas_owner;
ALTER FUNCTION saas_vzor.current_tenant_id() OWNER TO saas_owner;
ALTER TABLE    saas_vzor.tenant OWNER TO saas_owner;
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

-- EN: 5a. Onboarding: synthetic tenants A and B are created by saas_provisioner.
-- CZ: 5a. Onboarding: syntetické tenanty A a B zakládá saas_provisioner.
SET LOCAL ROLE saas_provisioner;
INSERT INTO saas_vzor.tenant (tenant_id, nazev) VALUES
    ('11111111-1111-4111-8111-111111111111', 'Vzorová elektro firma A (syntetická)'),
    ('22222222-2222-4222-8222-222222222222', 'Vzorová elektro firma B (syntetická)');

-- EN: 5b. Sign-in: the authentication gateway issues session tokens. Fixed values are used
--     here only to keep the pattern readable; in production the token is gen_random_uuid(),
--     lives for minutes and is handed to the application over the authenticated channel.
--     The third row is an already expired token of tenant A (used by TEST 7).
-- CZ: 5b. Přihlášení: autentizační brána vydává tokeny relací. Pevné hodnoty jsou zde jen
--     kvůli čitelnosti vzoru; v provozu je token gen_random_uuid(), žije minuty a aplikaci
--     se předává ověřeným kanálem. Třetí řádek je již prošlý token tenanta A (pro TEST 7).
SET LOCAL ROLE saas_auth;
INSERT INTO saas_vzor.tenant_session (token, tenant_id, expires_at) VALUES
    ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '11111111-1111-4111-8111-111111111111', now() + interval '15 minutes'),
    ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '22222222-2222-4222-8222-222222222222', now() + interval '15 minutes'),
    ('cccccccc-cccc-4ccc-8ccc-cccccccccccc', '11111111-1111-4111-8111-111111111111', now() - interval '1 minute');

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
        INSERT INTO saas_vzor.tenant_session (tenant_id, expires_at)
        VALUES ('22222222-2222-4222-8222-222222222222', now() + interval '15 minutes');
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
--     SUPERUSER / BYPASSRLS among the four roles, and no SECURITY DEFINER function
--     without a pinned search_path.
-- CZ: TEST 12 — kontrola katalogu: RLS zapnuté a vynucené na každé běžné i dělené tabulce,
--     každá taková tabulka má omezující politiku TO PUBLIC, 0 materializovaných pohledů,
--     žádná ze čtyř rolí není SUPERUSER / BYPASSRLS a žádná funkce SECURITY DEFINER
--     nemá nepřipnutý search_path.
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
       AND f.proconfig IS NULL;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 12 FAIL: % SECURITY DEFINER functions without pinned settings', n;
    END IF;
    RAISE NOTICE 'TEST 12 PASS: RLS forced, restrictive guard TO PUBLIC everywhere, 0 matviews, no BYPASSRLS';
END
$$;

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
--     (7) this file has not been executed — every statement must be proven in a
--         throw-away database before it is used as a template.
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
--     (7) tento soubor nebyl spuštěn — každý příkaz je nutné před použitím jako předlohy
--         prokázat v databázi určené k zahození.
ROLLBACK;
