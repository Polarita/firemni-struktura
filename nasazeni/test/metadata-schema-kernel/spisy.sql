\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.ciselne_rady_test',0));
CREATE SCHEMA IF NOT EXISTS polarita_test_spisy AUTHORIZATION pol_metadata_ddl;
SET LOCAL ROLE pol_metadata_ddl;
REVOKE ALL ON SCHEMA polarita_test_spisy FROM PUBLIC;
GRANT USAGE ON SCHEMA polarita_test_spisy TO pol_metadata_api, pol_metadata_read;
CREATE TABLE IF NOT EXISTS polarita_test_spisy.pobocka (
    branch_id integer PRIMARY KEY CHECK(branch_id BETWEEN 101 AND 999)
);
INSERT INTO polarita_test_spisy.pobocka VALUES (101) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS polarita_test_spisy.rada (
    rok integer PRIMARY KEY CHECK(rok BETWEEN 2000 AND 9999),
    posledni integer NOT NULL CHECK(posledni BETWEEN 0 AND 99999)
);
CREATE TABLE IF NOT EXISTS polarita_test_spisy.spis (
    pozadavek uuid PRIMARY KEY,
    rok integer NOT NULL REFERENCES polarita_test_spisy.rada,
    cislo integer NOT NULL CHECK(cislo BETWEEN 1 AND 99999),
    branch_id integer NOT NULL REFERENCES polarita_test_spisy.pobocka,
    zalozeno timestamptz NOT NULL DEFAULT now(),
    UNIQUE (rok,cislo)
);
CREATE OR REPLACE VIEW polarita_test_spisy.karty AS
SELECT pozadavek,branch_id,zalozeno,
       'POL-' || rok || '-' || lpad(cislo::text,5,'0') AS case_id,
       'POL-' || branch_id || '-' || rok || '-' || lpad(cislo::text,5,'0') AS alias
FROM polarita_test_spisy.spis;
CREATE OR REPLACE FUNCTION polarita_test_spisy.zaloz(klic uuid,pobocka integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE
    novy_rok integer := extract(year from now() at time zone 'Europe/Prague');
    dalsi integer;
    karta polarita_test_spisy.karty%ROWTYPE;
BEGIN
    IF klic IS NULL OR pobocka IS NULL OR NOT EXISTS (
        SELECT FROM polarita_test_spisy.pobocka AS p WHERE p.branch_id=zaloz.pobocka
    ) THEN RETURN jsonb_build_object('chyba','pobocka'); END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(klic::text,0));
    SELECT * INTO karta FROM polarita_test_spisy.karty WHERE pozadavek=klic;
    IF FOUND THEN
        IF karta.branch_id<>pobocka THEN RETURN jsonb_build_object('chyba','kolize'); END IF;
        RETURN to_jsonb(karta);
    END IF;
    INSERT INTO polarita_test_spisy.rada VALUES(novy_rok,0) ON CONFLICT DO NOTHING;
    SELECT posledni+1 INTO dalsi FROM polarita_test_spisy.rada WHERE rok=novy_rok FOR UPDATE;
    IF dalsi>99999 THEN RETURN jsonb_build_object('chyba','vycerpano'); END IF;
    UPDATE polarita_test_spisy.rada SET posledni=dalsi WHERE rok=novy_rok;
    INSERT INTO polarita_test_spisy.spis(pozadavek,rok,cislo,branch_id) VALUES (klic,novy_rok,dalsi,pobocka);
    SELECT * INTO STRICT karta FROM polarita_test_spisy.karty WHERE pozadavek=klic;
    RETURN to_jsonb(karta);
END $$;
REVOKE ALL ON FUNCTION polarita_test_spisy.zaloz(uuid,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION polarita_test_spisy.zaloz(uuid,integer) TO pol_metadata_api;
GRANT SELECT ON polarita_test_spisy.karty TO pol_metadata_read, pol_metadata_api;
COMMIT;
