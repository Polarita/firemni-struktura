BEGIN;
CREATE SCHEMA IF NOT EXISTS polarita_test_lhutnik;
REVOKE ALL ON SCHEMA polarita_test_lhutnik FROM PUBLIC;
CREATE TABLE IF NOT EXISTS polarita_test_lhutnik.zkousky (
    protokol uuid PRIMARY KEY,
    rozhodnuti uuid NOT NULL UNIQUE,
    spis text NOT NULL UNIQUE CHECK (spis ~ '^POL-[0-9]+$'),
    provedeno date NOT NULL,
    platnost_do date NOT NULL CHECK (platnost_do = (provedeno + interval '3 years')::date)
);
REVOKE ALL ON polarita_test_lhutnik.zkousky FROM PUBLIC;
GRANT USAGE ON SCHEMA polarita_test_lhutnik TO db_erp_lhutnik, pol_metadata_api;
GRANT SELECT, INSERT ON polarita_test_lhutnik.zkousky TO db_erp_lhutnik;
GRANT SELECT (spis, platnost_do) ON polarita_test_lhutnik.zkousky TO pol_metadata_api;
COMMIT;
