\set ON_ERROR_STOP on
BEGIN;
SET LOCAL ROLE pol_metadata_ddl;
CREATE TABLE IF NOT EXISTS polarita_test_spisy.vykop_metodika (
    kod text PRIMARY KEY, telo jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS polarita_test_spisy.vykop_trasa (
    spis uuid NOT NULL REFERENCES polarita_test_spisy.spis,
    trasa text NOT NULL CHECK(trasa ~ '^[A-Z0-9][A-Z0-9-]{0,63}$'),
    revize text NOT NULL CHECK(revize ~ '^[a-f0-9]{64}$'),
    metodika text NOT NULL REFERENCES polarita_test_spisy.vykop_metodika,
    projekt jsonb NOT NULL,
    doklady jsonb NOT NULL,
    PRIMARY KEY (spis,trasa)
);
CREATE TABLE IF NOT EXISTS polarita_test_spisy.vykop_uvolneni (
    spis uuid NOT NULL, trasa text NOT NULL, podklady text NOT NULL,
    cas timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (spis,trasa,podklady),
    FOREIGN KEY (spis,trasa) REFERENCES polarita_test_spisy.vykop_trasa
);
CREATE OR REPLACE FUNCTION polarita_test_spisy.vykopy(kod text)
RETURNS SETOF jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
SELECT jsonb_build_object('case_id',k.case_id,'trasa',t.trasa,'projekt',t.projekt,'revize',t.revize,
    'metodika',m.telo,'doklady',t.doklady,'den',(now() AT TIME ZONE 'Europe/Prague')::date,
    'archiv',coalesce((SELECT jsonb_object_agg(a.otisk,a.dokument ORDER BY a.dokument)
        FROM polarita_test_spisy.prijem_sanonu a WHERE a.spis=t.spis AND a.stav='ocr-hotovo'
        AND a.vystup_sha256 IS NOT NULL AND a.dokument IS NOT NULL
        AND (a.otisk=t.doklady->>'mapa' OR EXISTS (SELECT FROM jsonb_each(t.doklady->'vyjadreni') v
            WHERE v.value->>'sha256'=a.otisk))), '{}'::jsonb))
FROM polarita_test_spisy.vykop_trasa t JOIN polarita_test_spisy.karty k ON t.spis=k.pozadavek
JOIN polarita_test_spisy.vykop_metodika m ON m.kod=t.metodika WHERE k.case_id=kod ORDER BY t.trasa
$$;
CREATE OR REPLACE FUNCTION polarita_test_spisy.uloz_vykop(kod text, oznaceni text, ocekavane jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE spis_id uuid; stav jsonb;
BEGIN
    SELECT t.spis INTO spis_id FROM polarita_test_spisy.vykop_trasa t
        JOIN polarita_test_spisy.karty k ON k.pozadavek=t.spis
        JOIN polarita_test_spisy.vykop_metodika m ON m.kod=t.metodika
        WHERE k.case_id=kod AND t.trasa=oznaceni FOR SHARE OF t,m;
    IF NOT FOUND THEN RETURN false; END IF;
    SELECT v INTO STRICT stav FROM polarita_test_spisy.vykopy(kod) v WHERE v->>'trasa'=oznaceni;
    IF stav IS DISTINCT FROM ocekavane THEN RETURN false; END IF;
    INSERT INTO polarita_test_spisy.vykop_uvolneni(spis,trasa,podklady)
        VALUES(spis_id,oznaceni,encode(sha256(convert_to(stav::text,'UTF8')),'hex')) ON CONFLICT DO NOTHING;
    RETURN true;
END $$;
REVOKE ALL ON FUNCTION polarita_test_spisy.vykopy(text),polarita_test_spisy.uloz_vykop(text,text,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION polarita_test_spisy.vykopy(text) TO pol_metadata_api,pol_metadata_read;
GRANT EXECUTE ON FUNCTION polarita_test_spisy.uloz_vykop(text,text,jsonb) TO pol_metadata_api;
COMMIT;
