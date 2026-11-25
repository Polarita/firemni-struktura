\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.ciselne_rady_test',0));
SET LOCAL ROLE pol_metadata_ddl;
CREATE TABLE IF NOT EXISTS polarita_test_spisy.vyrobni_rada (
    rok integer PRIMARY KEY CHECK (rok BETWEEN 2000 AND 9999),
    posledni integer NOT NULL CHECK (posledni BETWEEN 0 AND 99999)
);
CREATE TABLE IF NOT EXISTS polarita_test_spisy.rozvadec (
    pozadavek uuid PRIMARY KEY,
    spis uuid NOT NULL REFERENCES polarita_test_spisy.spis(pozadavek),
    oznaceni text NOT NULL CHECK (oznaceni ~ '^[A-Z0-9][A-Z0-9+_.-]{0,39}$'),
    rok integer NOT NULL REFERENCES polarita_test_spisy.vyrobni_rada,
    poradi integer NOT NULL CHECK (poradi BETWEEN 1 AND 99999),
    UNIQUE (rok, poradi),
    UNIQUE (spis, oznaceni)
);
CREATE OR REPLACE VIEW polarita_test_spisy.vyrobni_cisla AS
    SELECT r.pozadavek, k.case_id, r.oznaceni, r.rok, r.poradi,
           'RZ-' || r.rok || '-' || lpad(r.poradi::text,5,'0') AS vyrobni_cislo
    FROM polarita_test_spisy.rozvadec r JOIN polarita_test_spisy.karty k ON k.pozadavek=r.spis;
CREATE OR REPLACE FUNCTION polarita_test_spisy.pridel_vyrobni_cislo(p_id uuid, p_spis uuid, p_oznaceni text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE
    rok_vyroby integer := extract(year FROM statement_timestamp() AT TIME ZONE 'Europe/Prague');
    predchozi polarita_test_spisy.rozvadec%ROWTYPE;
    dalsi integer;
BEGIN
    IF p_id IS NULL OR p_spis IS NULL OR p_oznaceni IS NULL OR p_oznaceni !~ '^[A-Z0-9][A-Z0-9+_.-]{0,39}$'
        OR NOT EXISTS (SELECT FROM polarita_test_spisy.spis WHERE pozadavek=p_spis) THEN
        RAISE EXCEPTION 'Neplatný požadavek, spis nebo označení testovacího rozváděče' USING ERRCODE='22023';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(p_id::text,0));
    SELECT * INTO predchozi FROM polarita_test_spisy.rozvadec WHERE pozadavek=p_id;
    IF FOUND THEN
        IF predchozi.spis <> p_spis OR predchozi.oznaceni <> p_oznaceni THEN
            RAISE EXCEPTION 'Stejný požadavek označuje jiný rozváděč' USING ERRCODE='23505';
        END IF;
    ELSE
        INSERT INTO polarita_test_spisy.vyrobni_rada VALUES (rok_vyroby,0) ON CONFLICT DO NOTHING;
        SELECT posledni+1 INTO STRICT dalsi FROM polarita_test_spisy.vyrobni_rada WHERE rok=rok_vyroby FOR UPDATE;
        IF dalsi>99999 THEN RAISE EXCEPTION 'Vyčerpaná výrobní řada roku'; END IF;
        INSERT INTO polarita_test_spisy.rozvadec VALUES(p_id,p_spis,p_oznaceni,rok_vyroby,dalsi);
        UPDATE polarita_test_spisy.vyrobni_rada SET posledni=dalsi WHERE rok=rok_vyroby;
    END IF;
    RETURN (SELECT vyrobni_cislo FROM polarita_test_spisy.vyrobni_cisla WHERE pozadavek=p_id);
END $$;
REVOKE ALL ON FUNCTION polarita_test_spisy.pridel_vyrobni_cislo(uuid,uuid,text) FROM PUBLIC;
-- Čísla přiděluje pouze řízený import. Webové a MCP účty smějí číst registr.
GRANT SELECT ON polarita_test_spisy.vyrobni_cisla TO pol_metadata_read, pol_metadata_api;
COMMIT;
