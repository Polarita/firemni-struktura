BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita/akademie/prehled-test', 0));
CREATE SCHEMA IF NOT EXISTS akademie_test;
CREATE SCHEMA IF NOT EXISTS akademie_prehled_test;
REVOKE ALL ON SCHEMA akademie_test, akademie_prehled_test FROM PUBLIC;
CREATE TABLE IF NOT EXISTS akademie_test.protokol (
    protokol uuid PRIMARY KEY,
    person_no uuid NOT NULL,
    druh text NOT NULL CHECK (druh IN ('pouceni','elektrotechnik','vedouci')),
    provedeno timestamptz NOT NULL,
    platnost_do date NOT NULL,
    uspel boolean NOT NULL,
    komise uuid[] NOT NULL,
    sifrovany_obsah bytea NOT NULL CHECK (octet_length(sifrovany_obsah) > 0),
    archiv_sha256 bytea CHECK (octet_length(archiv_sha256) = 32),
    UNIQUE (person_no, druh, provedeno),
    CHECK (platnost_do BETWEEN (provedeno AT TIME ZONE 'Europe/Prague')::date
                           AND ((provedeno AT TIME ZONE 'Europe/Prague')::date + INTERVAL '3 years')::date),
    CHECK ((druh = 'pouceni' AND cardinality(komise) = 0) OR
           (druh <> 'pouceni' AND cardinality(komise) = 3 AND array_ndims(komise) = 1 AND array_lower(komise, 1) = 1
            AND array_position(komise, NULL) IS NULL AND komise[1] <> komise[2] AND komise[2] <> komise[3]
            AND komise[1] <> komise[3]))
);
-- Přístupová vrstva rozlišuje jednotlivé stupně. Starší úspěch nepřepíše novější neúspěšný výsledek.
CREATE OR REPLACE VIEW akademie_test.posledni WITH (security_barrier=true) AS
    SELECT DISTINCT ON (person_no, druh) person_no, druh,
        (uspel AND platnost_do >= (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Prague')::date) AS zpusobily
      FROM akademie_test.protokol
     WHERE archiv_sha256 IS NOT NULL AND provedeno <= CURRENT_TIMESTAMP
     ORDER BY person_no, druh, provedeno DESC;
CREATE OR REPLACE VIEW akademie_prehled_test.pouceni WITH (security_barrier=true) AS
    SELECT person_no, zpusobily FROM akademie_test.posledni WHERE druh='pouceni';
CREATE OR REPLACE VIEW akademie_prehled_test.elektrotechnik WITH (security_barrier=true) AS
    SELECT person_no, zpusobily FROM akademie_test.posledni WHERE druh='elektrotechnik';
CREATE OR REPLACE VIEW akademie_prehled_test.vedouci WITH (security_barrier=true) AS
    SELECT person_no, zpusobily FROM akademie_test.posledni WHERE druh='vedouci';
REVOKE ALL ON ALL TABLES IN SCHEMA akademie_test FROM PUBLIC, polarita_ai_masked;
REVOKE ALL ON SCHEMA akademie_test FROM polarita_ai_masked;
REVOKE ALL ON ALL TABLES IN SCHEMA akademie_prehled_test FROM PUBLIC, polarita_ai_masked;
GRANT USAGE ON SCHEMA akademie_prehled_test TO polarita_ai_masked;
GRANT SELECT ON akademie_prehled_test.pouceni, akademie_prehled_test.elektrotechnik,
    akademie_prehled_test.vedouci TO polarita_ai_masked;
GRANT USAGE ON SCHEMA akademie_test TO db_gdpr_zkousky;
GRANT INSERT, SELECT ON akademie_test.protokol TO db_gdpr_zkousky;
GRANT UPDATE (archiv_sha256) ON akademie_test.protokol TO db_gdpr_zkousky;
COMMIT;
