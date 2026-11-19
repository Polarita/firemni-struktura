-- =====================================================================================
-- rls-vzor.sql — Polarita Elektro Cloud · Blok 19 (S7) · Verze 2.8 (Polarita-2.8)
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
-- EN: Production layout (PRIMARY MODEL): one shared application schema where every table
--     carries a compound key (tenant_id, id), ENABLE + FORCE ROW LEVEL SECURITY, an
--     AS RESTRICTIVE tenant guard policy (cannot be weakened by future permissive
--     policies) and per-tenant DEK keys in OpenBao. Dedicated per-tenant schemas
--     remain an optional enterprise isolation mode only — NOT the default, so PgBouncer
--     pooling and schema migrations stay single-path.
-- CZ: Produkční uspořádání (PRIMÁRNÍ MODEL): jedno sdílené aplikační schéma, kde každá
--     tabulka nese složený klíč (tenant_id, id), ENABLE + FORCE ROW LEVEL SECURITY,
--     omezující politiku AS RESTRICTIVE (nelze ji oslabit přidáním jiné PERMISSIVE
--     politiky) a vlastní šifrovací klíč tenanta v OpenBao. Vyhrazené schéma pro
--     jediného tenanta je jen volitelný nadstandard, nikoli výchozí model (aby fungovalo
--     sdružování spojení PgBouncerem a jednotné migrace).
-- =====================================================================================

BEGIN;

-- -------------------------------------------------------------------------------------
-- 1. Roles / Role
-- -------------------------------------------------------------------------------------
-- EN: saas_owner owns the objects and runs migrations; it cannot log in.
--     saas_app is the only role the application connects with. Neither role is a
--     superuser and neither has BYPASSRLS. The password / certificate of saas_app
--     is provisioned from OpenBao, never written into SQL files.
-- CZ: saas_owner vlastní objekty a spouští migrace; nemůže se přihlásit.
--     saas_app je jediná role, kterou se připojuje aplikace. Žádná z rolí není
--     superuser a žádná nemá BYPASSRLS. Heslo / certifikát role saas_app se
--     dodává z OpenBao, nikdy se nezapisuje do SQL souborů.
CREATE ROLE saas_owner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE saas_app   LOGIN   NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;

-- -------------------------------------------------------------------------------------
-- 2. Schema and tables / Schéma a tabulky
-- -------------------------------------------------------------------------------------
CREATE SCHEMA saas_vzor;
REVOKE ALL ON SCHEMA saas_vzor FROM PUBLIC;

-- EN: Safe UUID reader for app.tenant_id. Missing, empty or malformed values return NULL
--     so queries always fail closed to 0 rows without leaking parse errors.
-- CZ: Bezpečné čtení UUID z app.tenant_id. Chybějící, prázdná i neplatná hodnota vrátí
--     NULL, takže dotaz vždy selže bezpečně do 0 řádků bez úniku chyby převodu.
CREATE FUNCTION saas_vzor.current_tenant_id()
RETURNS uuid
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    raw text;
BEGIN
    raw := NULLIF(current_setting('app.tenant_id', true), '');
    IF raw IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN raw::uuid;
EXCEPTION
    WHEN invalid_text_representation THEN
        RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION saas_vzor.current_tenant_id() FROM PUBLIC;

-- EN: Tenant registry (one row per subscribing company).
-- CZ: Registr tenantů (jeden řádek na předplatitelskou firmu).
CREATE TABLE saas_vzor.tenant (
    tenant_id uuid PRIMARY KEY,
    nazev     text NOT NULL
);

-- EN: Sample business table (simplified "building" from the Digital Building Book).
--     Uses UUID primary key (tenant_id, objekt_id) to avoid global sequence leakage
--     across tenants; tenant_id defaults from current_tenant_id() of the transaction.
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

-- EN: Synthetic tenants A and B (inserted by the administrator before RLS is on).
-- CZ: Syntetičtí tenanti A a B (vkládá administrátor před zapnutím RLS).
INSERT INTO saas_vzor.tenant (tenant_id, nazev) VALUES
    ('11111111-1111-4111-8111-111111111111', 'Vzorová elektro firma A (syntetická)'),
    ('22222222-2222-4222-8222-222222222222', 'Vzorová elektro firma B (syntetická)');

-- -------------------------------------------------------------------------------------
-- 3. Row-Level Security
-- -------------------------------------------------------------------------------------
-- EN: ENABLE turns RLS on; FORCE makes it apply to the table owner as well.
--     Without FORCE the owner (saas_owner) would silently see every tenant.
-- CZ: ENABLE zapíná RLS; FORCE jej vynutí i pro vlastníka tabulky.
--     Bez FORCE by vlastník (saas_owner) tiše viděl všechny tenanty.
ALTER TABLE saas_vzor.tenant ENABLE ROW LEVEL SECURITY;
ALTER TABLE saas_vzor.tenant FORCE  ROW LEVEL SECURITY;
ALTER TABLE saas_vzor.objekt ENABLE ROW LEVEL SECURITY;
ALTER TABLE saas_vzor.objekt FORCE  ROW LEVEL SECURITY;

-- EN: Primary tenant guard is AS RESTRICTIVE on both tables: PostgreSQL requires ALL
--     restrictive policies to pass regardless of any permissive policy added later.
-- CZ: Hlavní pojistka je AS RESTRICTIVE na obou tabulkách: PostgreSQL vyžaduje splnění
--     všech RESTRICTIVE politik bez ohledu na později přidané PERMISSIVE politiky.
CREATE POLICY tenant_guard ON saas_vzor.objekt
    AS RESTRICTIVE
    FOR ALL
    TO saas_app
    USING      (tenant_id = saas_vzor.current_tenant_id())
    WITH CHECK (tenant_id = saas_vzor.current_tenant_id());

CREATE POLICY objekt_app_access ON saas_vzor.objekt
    AS PERMISSIVE
    FOR ALL
    TO saas_app
    USING      (true)
    WITH CHECK (true);

CREATE POLICY tenant_self_guard ON saas_vzor.tenant
    AS RESTRICTIVE
    FOR SELECT
    TO saas_app
    USING (tenant_id = saas_vzor.current_tenant_id());

CREATE POLICY tenant_self_read ON saas_vzor.tenant
    AS PERMISSIVE
    FOR SELECT
    TO saas_app
    USING (true);

-- -------------------------------------------------------------------------------------
-- 4. Privileges and ownership / Oprávnění a vlastnictví
-- -------------------------------------------------------------------------------------
-- EN: Least privilege. Revoke PUBLIC defaults, no TRUNCATE, no tenant registry writes.
-- CZ: Nejmenší oprávnění. Zrušit výchozí PUBLIC práva, žádný TRUNCATE, žádný zápis do registru.
REVOKE ALL ON ALL TABLES IN SCHEMA saas_vzor FROM PUBLIC;
GRANT USAGE ON SCHEMA saas_vzor TO saas_app;
GRANT EXECUTE ON FUNCTION saas_vzor.current_tenant_id() TO saas_app;
GRANT SELECT ON saas_vzor.tenant TO saas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON saas_vzor.objekt TO saas_app;
GRANT SELECT ON saas_vzor.v_objekt_clean_room TO saas_app;

ALTER SCHEMA   saas_vzor OWNER TO saas_owner;
ALTER FUNCTION saas_vzor.current_tenant_id() OWNER TO saas_owner;
ALTER TABLE    saas_vzor.tenant OWNER TO saas_owner;
ALTER TABLE    saas_vzor.objekt OWNER TO saas_owner;
ALTER VIEW     saas_vzor.v_objekt_clean_room OWNER TO saas_owner;

-- -------------------------------------------------------------------------------------
-- 5. Seed data written THROUGH the policy / Vzorová data zapsaná PŘES politiku
-- -------------------------------------------------------------------------------------
-- EN: From here on the script acts as the application role. A superuser always
--     bypasses RLS, so tests run as an administrator would prove nothing.
--     The application sets the tenant per transaction with set_config(..., true)
--     (= SET LOCAL), taking the value from the verified OIDC token — never from
--     client input and never per session (pooled connections are shared).
-- CZ: Odtud skript vystupuje jako aplikační role. Superuser RLS vždy obchází,
--     takže testy spuštěné administrátorem by nic nedokázaly.
--     Aplikace nastavuje tenanta pro každou transakci přes set_config(..., true)
--     (= SET LOCAL) a hodnotu bere z ověřeného tokenu OIDC — nikdy ze vstupu
--     klienta a nikdy na celou relaci (spojení z poolu jsou sdílená).
SET LOCAL ROLE saas_app;

SELECT set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
INSERT INTO saas_vzor.objekt (nazev) VALUES
    ('Bytový dům Vzorová 1 (tenant A)'),
    ('Výrobní hala Vzorová 2 (tenant A)');

SELECT set_config('app.tenant_id', '22222222-2222-4222-8222-222222222222', true);
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
    PERFORM set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
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
    PERFORM set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
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
    PERFORM set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
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
    PERFORM set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
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
    PERFORM set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
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
    PERFORM set_config('app.tenant_id', '22222222-2222-4222-8222-222222222222', true);
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

-- EN: TEST 7 — RESET app.tenant_id & malformed UUID ('not-a-uuid'): 0 rows visible, no insert (FAIL_CLOSED).
-- CZ: TEST 7 — RESET app.tenant_id a neplatné UUID ('not-a-uuid'): 0 řádků, zápis zakázán (FAIL_CLOSED).
DO $$
DECLARE
    n bigint;
BEGIN
    RESET "app.tenant_id";
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 7 FAIL: % rows visible after RESET app.tenant_id', n;
    END IF;
    PERFORM set_config('app.tenant_id', 'not-a-uuid', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 7 FAIL: % rows visible with malformed UUID', n;
    END IF;
    BEGIN
        INSERT INTO saas_vzor.objekt (nazev) VALUES ('objekt bez tenanta');
    EXCEPTION
        WHEN insufficient_privilege OR not_null_violation THEN
            RAISE NOTICE 'TEST 7 PASS: unset / invalid tenant = 0 rows / neplatny tenant zadna data';
            RETURN;
    END;
    RAISE EXCEPTION 'TEST 7 FAIL: insert without valid tenant succeeded';
END
$$;

-- EN: TEST 8 — Clean Room security_invoker view & least-privilege blocks on tenant registry / TRUNCATE.
-- CZ: TEST 8 — Clean Room pohled (security_invoker) a zákaz zápisu do registru tenantů / TRUNCATE.
DO $$
DECLARE
    cnt bigint;
BEGIN
    PERFORM set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
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

-- EN: TEST 9 — FORCE ROW LEVEL SECURITY: even the table owner sees nothing,
--     because no policy is granted to it (default deny).
-- CZ: TEST 9 — FORCE ROW LEVEL SECURITY: ani vlastník tabulky nevidí nic,
--     protože pro něj neexistuje žádná politika (výchozí zákaz).
SET LOCAL ROLE saas_owner;
DO $$
DECLARE
    n bigint;
BEGIN
    PERFORM set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
    SELECT count(*) INTO n FROM saas_vzor.objekt;
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 9 FAIL: table owner sees % rows despite FORCE RLS', n;
    END IF;
    RAISE NOTICE 'TEST 9 PASS: owner is subject to RLS / vlastnik podleha RLS';
END
$$;

-- EN: TEST 10 — catalog check: RLS enabled and forced on every regular/partitioned
--     table, 0 unguarded materialized views, and no SUPERUSER / BYPASSRLS role.
-- CZ: TEST 10 — kontrola katalogu: RLS zapnuté a vynucené na každé běžné i dělené
--     tabulce, 0 nechráněných materializovaných pohledů a žádná role SUPERUSER / BYPASSRLS.
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
        RAISE EXCEPTION 'TEST 10 FAIL: % tables without enabled and forced RLS', n;
    END IF;
    SELECT count(*) INTO n
      FROM pg_class c
      JOIN pg_namespace s ON s.oid = c.relnamespace
     WHERE s.nspname = 'saas_vzor'
       AND c.relkind = 'm';
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 10 FAIL: % unguarded materialized views in tenant schema', n;
    END IF;
    SELECT count(*) INTO n
      FROM pg_roles
     WHERE rolname IN ('saas_owner', 'saas_app')
       AND (rolsuper OR rolbypassrls);
    IF n <> 0 THEN
        RAISE EXCEPTION 'TEST 10 FAIL: % roles are superuser or have BYPASSRLS', n;
    END IF;
    RAISE NOTICE 'TEST 10 PASS: RLS forced on all tables, 0 matviews, no BYPASSRLS';
END
$$;

-- -------------------------------------------------------------------------------------
-- 7. Clean-up / Úklid
-- -------------------------------------------------------------------------------------
-- EN: The pattern leaves nothing behind. In a real migration the DDL from
--     sections 1–4 is generated by metadata-schema-kernel and committed; the
--     tests from section 6 run in Gitea Actions before every release.
--     Known limits to cover elsewhere: superusers and BYPASSRLS roles always
--     bypass RLS; foreign-key and unique checks are not filtered by RLS;
--     backups (pg_dump) need a dedicated, audited procedure.
-- CZ: Vzor po sobě nic nezanechá. Ve skutečné migraci generuje DDL z oddílů 1–4
--     modul metadata-schema-kernel a potvrzuje se; testy z oddílu 6 běží
--     v Gitea Actions před každým vydáním.
--     Známé meze, které je nutné ošetřit jinde: superuser a role s BYPASSRLS
--     RLS vždy obcházejí; kontroly cizích klíčů a unikátnosti RLS nefiltruje;
--     zálohy (pg_dump) potřebují vyhrazený auditovaný postup.
ROLLBACK;
