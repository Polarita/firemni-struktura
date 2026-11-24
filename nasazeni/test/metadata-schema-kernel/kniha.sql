\set ON_ERROR_STOP on
BEGIN;
SET LOCAL ROLE pol_metadata_ddl;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.kniha_objektu',0));
CREATE TABLE IF NOT EXISTS polarita_test_spisy.revize_objektu (
    spis uuid NOT NULL REFERENCES polarita_test_spisy.spis(pozadavek),
    objekt text NOT NULL CHECK (objekt ~ '^[A-Z0-9][A-Z0-9_-]{0,47}$'),
    zarizeni text NOT NULL CHECK (zarizeni ~ '^[A-Z0-9][A-Z0-9_-]{0,47}$'),
    revize date NOT NULL,
    upozornit date NOT NULL,
    platnost date NOT NULL,
    priloha uuid NOT NULL REFERENCES polarita_test_spisy.prijem_sanonu,
    zapsano timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (spis,objekt,zarizeni,revize),
    CHECK (revize <= upozornit AND upozornit <= platnost)
);
CREATE OR REPLACE VIEW polarita_test_spisy.kniha_objektu AS
SELECT DISTINCT ON (r.spis,r.objekt,r.zarizeni) k.case_id,r.objekt,r.zarizeni,r.revize,r.upozornit,
       r.platnost,r.priloha,p.dokument,r.zapsano,
       CASE WHEN (now() AT TIME ZONE 'Europe/Prague')::date > r.platnost THEN 'po-lhute'
            WHEN (now() AT TIME ZONE 'Europe/Prague')::date >= r.upozornit THEN 'blizi-se'
            ELSE 've-lhute' END AS stav
FROM polarita_test_spisy.revize_objektu r
JOIN polarita_test_spisy.karty k ON k.pozadavek=r.spis
JOIN polarita_test_spisy.prijem_sanonu p ON p.priloha=r.priloha AND p.spis=r.spis
ORDER BY r.spis,r.objekt,r.zarizeni,r.revize DESC;

CREATE OR REPLACE FUNCTION polarita_test_spisy.zapis_revizi(kod text,ozn_objekt text,ozn_zarizeni text,
    zprava uuid,provedena date,pripomenout date,do_dne date)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE
    spis_id uuid;
    ulozena polarita_test_spisy.revize_objektu%ROWTYPE;
BEGIN
    IF provedena IS NULL OR pripomenout IS NULL OR do_dne IS NULL OR provedena > pripomenout
       OR pripomenout > do_dne OR provedena > (now() AT TIME ZONE 'Europe/Prague')::date
    THEN RETURN 'datum'; END IF;
    SELECT p.spis INTO spis_id FROM polarita_test_spisy.prijem_sanonu p
    JOIN polarita_test_spisy.karty k ON k.pozadavek=p.spis
    WHERE k.case_id=kod AND p.priloha=zprava AND p.dokument IS NOT NULL AND p.stav IN ('ocr-hotovo','ke-kontrole');
    IF NOT FOUND THEN RETURN 'doklad'; END IF;
    INSERT INTO polarita_test_spisy.revize_objektu(spis,objekt,zarizeni,revize,upozornit,platnost,priloha)
    VALUES(spis_id,ozn_objekt,ozn_zarizeni,provedena,pripomenout,do_dne,zprava) ON CONFLICT DO NOTHING;
    SELECT * INTO STRICT ulozena FROM polarita_test_spisy.revize_objektu
    WHERE spis=spis_id AND objekt=ozn_objekt AND zarizeni=ozn_zarizeni AND revize=provedena;
    IF (ulozena.priloha,ulozena.upozornit,ulozena.platnost) IS DISTINCT FROM (zprava,pripomenout,do_dne)
    THEN RETURN 'kolize'; END IF;
    RETURN 'ulozeno';
END $$;
REVOKE ALL ON FUNCTION polarita_test_spisy.zapis_revizi(text,text,text,uuid,date,date,date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION polarita_test_spisy.zapis_revizi(text,text,text,uuid,date,date,date) TO pol_metadata_api;
GRANT SELECT ON polarita_test_spisy.kniha_objektu TO pol_metadata_api,pol_metadata_read;
COMMIT;
