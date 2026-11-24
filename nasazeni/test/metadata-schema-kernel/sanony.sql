\set ON_ERROR_STOP on
BEGIN;
SET LOCAL ROLE pol_metadata_ddl;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.prijem_sanonu',0));
GRANT USAGE ON SCHEMA polarita_test_spisy TO pol_prijem_sanonu;
CREATE TABLE IF NOT EXISTS polarita_test_spisy.prijem_sanonu (
    priloha uuid PRIMARY KEY,
    spis uuid NOT NULL REFERENCES polarita_test_spisy.spis(pozadavek),
    otisk text NOT NULL CHECK (otisk ~ '^[a-f0-9]{64}$'),
    bajtu integer NOT NULL CHECK (bajtu BETWEEN 1 AND 67108864),
    prijato timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE OR REPLACE VIEW polarita_test_spisy.potvrzeni_sanonu AS
SELECT p.priloha,k.case_id,p.prijato,p.prijato + interval '48 hours' AS termin,p.bajtu
FROM polarita_test_spisy.prijem_sanonu p JOIN polarita_test_spisy.karty k ON k.pozadavek=p.spis;

CREATE OR REPLACE FUNCTION polarita_test_spisy.prijmi_sanon(kod text,id uuid,sha text,velikost integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE
    spis_id uuid;
    starsi polarita_test_spisy.prijem_sanonu%ROWTYPE;
BEGIN
    SELECT pozadavek INTO spis_id FROM polarita_test_spisy.karty WHERE case_id=kod;
    IF NOT FOUND THEN RETURN jsonb_build_object('chyba','spis'); END IF;
    INSERT INTO polarita_test_spisy.prijem_sanonu(priloha,spis,otisk,bajtu)
        VALUES (id,spis_id,sha,velikost) ON CONFLICT (priloha) DO NOTHING;
    SELECT * INTO STRICT starsi FROM polarita_test_spisy.prijem_sanonu WHERE priloha=id;
    IF (starsi.spis,starsi.otisk,starsi.bajtu) IS DISTINCT FROM (spis_id,sha,velikost) THEN
        RETURN jsonb_build_object('chyba','kolize');
    END IF;
    RETURN (SELECT to_jsonb(p) FROM polarita_test_spisy.potvrzeni_sanonu p WHERE p.priloha=id);
END $$;
REVOKE ALL ON FUNCTION polarita_test_spisy.prijmi_sanon(text,uuid,text,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION polarita_test_spisy.prijmi_sanon(text,uuid,text,integer) TO pol_prijem_sanonu;
GRANT SELECT ON polarita_test_spisy.potvrzeni_sanonu TO pol_metadata_api,pol_metadata_read;
COMMIT;
