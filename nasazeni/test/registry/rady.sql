\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.ciselne_rady_test',0));
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='pol_registr_ddl') THEN
        CREATE ROLE pol_registr_ddl NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='pol_registr_doklady') THEN
        CREATE ROLE pol_registr_doklady NOLOGIN;
    END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS polarita_registr_test AUTHORIZATION pol_registr_ddl;
SET LOCAL ROLE pol_registr_ddl;
REVOKE ALL ON SCHEMA polarita_registr_test FROM PUBLIC;
CREATE TABLE IF NOT EXISTS polarita_registr_test.rada (
    druh text NOT NULL CHECK (druh IN ('FAK','ORG-UOL','VYD')),
    rok integer NOT NULL CHECK (rok BETWEEN 2000 AND 9999),
    posledni integer NOT NULL CHECK (posledni BETWEEN 0 AND 99999),
    PRIMARY KEY (druh,rok)
);
CREATE TABLE IF NOT EXISTS polarita_registr_test.doklad (
    pozadavek uuid PRIMARY KEY,
    spis uuid NOT NULL,
    druh text NOT NULL,
    rok integer NOT NULL,
    poradi integer NOT NULL CHECK (poradi BETWEEN 1 AND 99999),
    podklad_sha256 text NOT NULL CHECK (podklad_sha256 ~ '^[a-f0-9]{64}$'),
    cislo text GENERATED ALWAYS AS (druh || '-' || rok::text || '-' || lpad(poradi::text,5,'0')) STORED,
    FOREIGN KEY (druh,rok) REFERENCES polarita_registr_test.rada,
    UNIQUE(druh,rok,poradi)
);
CREATE INDEX IF NOT EXISTS doklad_spis ON polarita_registr_test.doklad(spis);
CREATE OR REPLACE FUNCTION polarita_registr_test.pridel_doklad(klic uuid, k_spisu uuid, typ text, otisk text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE
    letos integer := extract(year FROM statement_timestamp() AT TIME ZONE 'Europe/Prague');
    vydany polarita_registr_test.doklad%ROWTYPE;
    dalsi integer;
BEGIN
    IF klic IS NULL OR k_spisu IS NULL OR typ IS NULL OR typ NOT IN ('FAK','ORG-UOL','VYD')
        OR otisk IS NULL OR otisk !~ '^[a-f0-9]{64}$' THEN
        RAISE EXCEPTION 'Neplatný požadavek na přidělení čísla' USING ERRCODE='22023';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(klic::text,0));
    SELECT * INTO vydany FROM polarita_registr_test.doklad WHERE pozadavek=klic;
    IF FOUND THEN
        IF (vydany.spis,vydany.druh,vydany.podklad_sha256) IS DISTINCT FROM (k_spisu,typ,otisk) THEN
            RAISE EXCEPTION 'Opakovaný požadavek má jiný podklad, spis nebo řadu' USING ERRCODE='23505';
        END IF;
        RETURN vydany.cislo;
    END IF;
    INSERT INTO polarita_registr_test.rada VALUES (typ,letos,0) ON CONFLICT DO NOTHING;
    SELECT posledni+1 INTO STRICT dalsi FROM polarita_registr_test.rada WHERE druh=typ AND rok=letos FOR UPDATE;
    IF dalsi>99999 THEN RAISE EXCEPTION 'Vyčerpaná řada dokladů'; END IF;
    INSERT INTO polarita_registr_test.doklad(pozadavek,spis,druh,rok,poradi,podklad_sha256)
        VALUES(klic,k_spisu,typ,letos,dalsi,otisk) RETURNING * INTO vydany;
    UPDATE polarita_registr_test.rada SET posledni=dalsi WHERE druh=typ AND rok=letos;
    RETURN vydany.cislo;
END $$;
REVOKE ALL ON FUNCTION polarita_registr_test.pridel_doklad(uuid,uuid,text,text) FROM PUBLIC;
GRANT USAGE ON SCHEMA polarita_registr_test TO pol_registr_doklady;
GRANT EXECUTE ON FUNCTION polarita_registr_test.pridel_doklad(uuid,uuid,text,text) TO pol_registr_doklady;
COMMIT;
