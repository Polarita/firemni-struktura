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
ALTER TABLE polarita_test_spisy.prijem_sanonu
    ADD COLUMN IF NOT EXISTS vystup_sha256 text CHECK (vystup_sha256 ~ '^[a-f0-9]{64}$'),
    ADD COLUMN IF NOT EXISTS uzavreno timestamptz,
    ADD COLUMN IF NOT EXISTS dokument bigint CHECK (dokument > 0),
    ADD COLUMN IF NOT EXISTS stav text NOT NULL DEFAULT 'v-karantene'
        CHECK (stav IN ('v-karantene','odmitnuto','ocr-hotovo','ke-kontrole'));
CREATE OR REPLACE VIEW polarita_test_spisy.potvrzeni_sanonu AS
SELECT p.priloha,k.case_id,p.prijato,p.prijato + interval '48 hours' AS termin,p.bajtu,p.stav,p.dokument
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
CREATE OR REPLACE VIEW polarita_test_spisy.fronta_archivu AS
SELECT p.priloha,k.case_id,p.otisk,p.bajtu,p.prijato FROM polarita_test_spisy.prijem_sanonu p
JOIN polarita_test_spisy.karty k ON k.pozadavek=p.spis WHERE p.stav='v-karantene';
GRANT SELECT ON polarita_test_spisy.fronta_archivu TO pol_prijem_sanonu;

CREATE OR REPLACE FUNCTION polarita_test_spisy.uzavri_ocr(id uuid,kod text,puvodni text,cisty text,doc bigint,stav_ocr text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    IF NOT (stav_ocr='odmitnuto' AND cisty IS NULL AND doc IS NULL
            OR stav_ocr IN ('ocr-hotovo','ke-kontrole') AND cisty IS NOT NULL AND doc IS NOT NULL)
       OR stav_ocr IS NULL THEN RETURN false; END IF;
    UPDATE polarita_test_spisy.prijem_sanonu p SET stav=stav_ocr,vystup_sha256=cisty,dokument=doc,
        uzavreno=CASE WHEN p.stav='v-karantene' THEN clock_timestamp() ELSE p.uzavreno END
        FROM polarita_test_spisy.karty k WHERE p.priloha=id AND p.spis=k.pozadavek AND k.case_id=kod AND p.otisk=puvodni
        AND (p.stav='v-karantene' OR (p.stav,p.vystup_sha256,p.dokument) IS NOT DISTINCT FROM (stav_ocr,cisty,doc));
    RETURN FOUND;
END $$;
REVOKE ALL ON FUNCTION polarita_test_spisy.uzavri_ocr(uuid,text,text,text,bigint,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION polarita_test_spisy.uzavri_ocr(uuid,text,text,text,bigint,text) TO pol_prijem_sanonu;
COMMIT;
