BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita/test/personalistika', 0));
CREATE SCHEMA IF NOT EXISTS hr_scenare_test;
CREATE SCHEMA IF NOT EXISTS hr_prehled_test;
REVOKE ALL ON SCHEMA hr_scenare_test, hr_prehled_test FROM PUBLIC;
CREATE TABLE IF NOT EXISTS hr_scenare_test.nastup (
    person_no uuid PRIMARY KEY,
    scenar text NOT NULL UNIQUE CHECK (scenar ~ '^ES-[0-9]+$'),
    rozhodnuti text NOT NULL CHECK (rozhodnuti IN ('ALLOW','BLOCK','FAIL_CLOSED')),
    duvod text NOT NULL CHECK (length(duvod) > 0),
    otisk bytea NOT NULL CHECK (octet_length(otisk) = 32)
);
CREATE OR REPLACE VIEW hr_prehled_test.zpusobilost WITH (security_barrier=true) AS
    SELECT person_no, rozhodnuti = 'ALLOW' AS zpusobily FROM hr_scenare_test.nastup;
REVOKE ALL ON SCHEMA hr_scenare_test, hr_prehled_test FROM polarita_ai_masked;
REVOKE ALL ON hr_scenare_test.nastup, hr_prehled_test.zpusobilost FROM PUBLIC, polarita_ai_masked;
GRANT USAGE ON SCHEMA hr_scenare_test TO db_hr_lide;
GRANT SELECT, INSERT, UPDATE, DELETE ON hr_scenare_test.nastup TO db_hr_lide;
GRANT USAGE ON SCHEMA hr_prehled_test TO polarita_ai_masked;
GRANT SELECT ON hr_prehled_test.zpusobilost TO polarita_ai_masked;

SET LOCAL ROLE db_hr_lide;
CREATE TEMP TABLE ocekavane ON COMMIT DROP AS
    SELECT person_no, scenar, rozhodnuti, duvod, decode(otisk,'hex') AS otisk
    FROM jsonb_to_recordset(:'vysledky'::jsonb)
        AS data(person_no uuid, scenar text, rozhodnuti text, duvod text, otisk text);
INSERT INTO hr_scenare_test.nastup SELECT * FROM ocekavane
    ON CONFLICT (person_no) DO UPDATE SET
        (scenar, rozhodnuti, duvod, otisk) = (excluded.scenar, excluded.rozhodnuti, excluded.duvod, excluded.otisk)
    WHERE (nastup.scenar, nastup.rozhodnuti, nastup.duvod, nastup.otisk)
          IS DISTINCT FROM (excluded.scenar, excluded.rozhodnuti, excluded.duvod, excluded.otisk);
DELETE FROM hr_scenare_test.nastup n WHERE NOT EXISTS (SELECT FROM ocekavane o WHERE o.person_no=n.person_no);
CREATE TEMP TABLE ocekavany_prehled ON COMMIT DROP AS
    SELECT person_no, rozhodnuti='ALLOW' AS zpusobily FROM ocekavane;
GRANT SELECT ON ocekavany_prehled TO polarita_ai_masked;

SET LOCAL ROLE polarita_ai_masked;
DO $$
BEGIN
    IF (SELECT array_agg(column_name::text ORDER BY ordinal_position) FROM information_schema.columns
         WHERE table_schema='hr_prehled_test' AND table_name='zpusobilost')
         IS DISTINCT FROM ARRAY['person_no', 'zpusobily'] THEN
        RAISE EXCEPTION 'Maskovaný přehled obsahuje neočekávané sloupce';
    END IF;
    IF EXISTS (SELECT * FROM hr_prehled_test.zpusobilost EXCEPT ALL SELECT * FROM ocekavany_prehled)
       OR EXISTS (SELECT * FROM ocekavany_prehled EXCEPT ALL SELECT * FROM hr_prehled_test.zpusobilost) THEN
        RAISE EXCEPTION 'Stav pracovníků v maskovaném pohledu neodpovídá předloze';
    END IF;
    BEGIN
        PERFORM duvod FROM hr_scenare_test.nastup;
        RAISE EXCEPTION 'Čtecí role získala důvody personálních rozhodnutí';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    IF has_table_privilege(current_user, 'hr_prehled_test.zpusobilost', 'INSERT,UPDATE,DELETE')
       OR has_schema_privilege(current_user, 'hr_prehled_test', 'CREATE') THEN
        RAISE EXCEPTION 'Čtecí role může změnit přehled';
    END IF;
END $$;
SELECT format('TEST db_hr_lide: %s scénářů nástupu, %s způsobilé, %s zablokovaných.',
              count(*), count(*) FILTER (WHERE zpusobily), count(*) FILTER (WHERE NOT zpusobily))
    FROM hr_prehled_test.zpusobilost;
COMMIT;
