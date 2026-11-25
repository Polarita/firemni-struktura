\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.ciselne_rady_test',0));
SET LOCAL ROLE pol_registr_ddl;
CREATE TABLE IF NOT EXISTS polarita_registr_test.isdoc (
    faktura uuid PRIMARY KEY REFERENCES polarita_registr_test.doklad,
    predavka uuid NOT NULL UNIQUE REFERENCES polarita_registr_test.doklad,
    podklad jsonb NOT NULL,
    soubor bytea NOT NULL CHECK(octet_length(soubor) BETWEEN 1 AND 1048576),
    predavka_xml bytea NOT NULL CHECK(octet_length(predavka_xml) BETWEEN 1 AND 2097152),
    soubor_sha256 text GENERATED ALWAYS AS (encode(sha256(soubor),'hex')) STORED,
    predavka_sha256 text GENERATED ALWAYS AS (encode(sha256(predavka_xml),'hex')) STORED
);
CREATE TABLE IF NOT EXISTS polarita_registr_test.davka_isdoc (
    sha256 text GENERATED ALWAYS AS (encode(sha256(obsah),'hex')) STORED PRIMARY KEY,
    obsah bytea NOT NULL
);
CREATE TABLE IF NOT EXISTS polarita_registr_test.tisk_faktury (
    faktura uuid PRIMARY KEY REFERENCES polarita_registr_test.isdoc(faktura),
    soubor bytea NOT NULL CHECK(octet_length(soubor) BETWEEN 1 AND 1048576),
    sha256 text GENERATED ALWAYS AS (encode(sha256(soubor),'hex')) STORED
);
CREATE TABLE IF NOT EXISTS polarita_registr_test.peppol (
    faktura uuid PRIMARY KEY REFERENCES polarita_registr_test.isdoc(faktura),
    soubor bytea NOT NULL CHECK(octet_length(soubor) BETWEEN 1 AND 1048576),
    sha256 text GENERATED ALWAYS AS (encode(sha256(soubor),'hex')) STORED
);
RESET ROLE;
CREATE OR REPLACE VIEW polarita_registr_test.soubory_spisu AS
    SELECT s.case_id, f.cislo, i.soubor_sha256 AS sha256,i.soubor AS obsah
    FROM polarita_registr_test.isdoc i JOIN polarita_registr_test.doklad f ON f.pozadavek=i.faktura AND f.druh='FAK'
    JOIN polarita_test_spisy.karty s ON s.pozadavek=f.spis
    UNION ALL
    SELECT s.case_id, u.cislo, i.predavka_sha256,i.predavka_xml
    FROM polarita_registr_test.isdoc i JOIN polarita_registr_test.doklad f ON f.pozadavek=i.faktura AND f.druh='FAK'
    JOIN polarita_registr_test.doklad u ON u.pozadavek=i.predavka AND u.druh='ORG-UOL' AND u.spis=f.spis
    JOIN polarita_test_spisy.karty s ON s.pozadavek=u.spis;
GRANT SELECT ON polarita_registr_test.soubory_spisu TO pol_metadata_api,pol_metadata_read;
CREATE OR REPLACE VIEW polarita_registr_test.tisk_spisu AS
    SELECT k.case_id,d.cislo,t.sha256,t.soubor AS obsah
    FROM polarita_registr_test.tisk_faktury t JOIN polarita_registr_test.doklad d ON d.pozadavek=t.faktura
    JOIN polarita_test_spisy.karty k ON k.pozadavek=d.spis;
GRANT SELECT ON polarita_registr_test.tisk_spisu TO pol_metadata_api,pol_metadata_read;
CREATE OR REPLACE VIEW polarita_registr_test.peppol_spisu AS
    SELECT k.case_id,d.cislo,t.sha256,t.soubor AS obsah
    FROM polarita_registr_test.peppol t JOIN polarita_registr_test.doklad d ON d.pozadavek=t.faktura
    JOIN polarita_test_spisy.karty k ON k.pozadavek=d.spis;
GRANT SELECT ON polarita_registr_test.peppol_spisu TO pol_metadata_api,pol_metadata_read;
COMMIT;
