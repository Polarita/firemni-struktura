-- Interní rozšíření Paperclipu. Pouze stavy vzorových spisů TEST.
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.decisions_test.v1', 0));
DO $$
DECLARE name text;
BEGIN
    IF current_database() <> 'db_paperclip' THEN RAISE EXCEPTION 'Chybná databáze'; END IF;
    FOREACH name IN ARRAY ARRAY['pol_decisions_owner', 'pol_decisions_proposer', 'pol_decisions_reviewer']
    LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', name);
        END IF;
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = name AND
                (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) THEN
            RAISE EXCEPTION 'Neočekávaná práva role %', name;
        END IF;
    END LOOP;
END $$;
GRANT USAGE ON SCHEMA polarita TO pol_decisions_proposer, pol_decisions_reviewer, pol_decisions_owner;
GRANT CREATE ON SCHEMA polarita TO pol_decisions_owner;
SET LOCAL ROLE pol_decisions_owner;
CREATE TABLE IF NOT EXISTS polarita.test_spis (
    cislo text PRIMARY KEY CHECK (cislo ~ '^TEST-POL-[0-9]{4}-[0-9]{5}$'),
    verze bigint NOT NULL DEFAULT 1 CHECK (verze > 0),
    stav text NOT NULL CHECK (stav IN ('rozpracován', 'ke kontrole', 'uzavřen'))
);
CREATE TABLE IF NOT EXISTS polarita.test_rozhodnuti (
    id uuid PRIMARY KEY,
    cislo text NOT NULL REFERENCES polarita.test_spis,
    verze_pred bigint NOT NULL,
    pred text NOT NULL,
    po text NOT NULL CHECK (po IN ('rozpracován', 'ke kontrole', 'uzavřen') AND po <> pred),
    fronta text NOT NULL CHECK (fronta IN ('URGENT','DENNI')),
    vytvoreno timestamptz NOT NULL,
    dostupne timestamptz NOT NULL,
    akce text CHECK (akce IN ('mutation_confirm','mutation_cancel')),
    rozhodnuto timestamptz,
    CHECK ((akce IS NULL) = (rozhodnuto IS NULL))
);
CREATE OR REPLACE FUNCTION polarita.test_okno(cas timestamptz, fronta text) RETURNS timestamptz
LANGUAGE plpgsql STABLE STRICT SET search_path = pg_catalog, pg_temp AS $$
DECLARE mistni timestamp := cas AT TIME ZONE 'Europe/Prague';
BEGIN
    IF fronta = 'URGENT' THEN RETURN cas; END IF;
    IF fronta <> 'DENNI' THEN RAISE EXCEPTION 'Neznámá fronta'; END IF;
    RETURN (CASE WHEN mistni::time <= time '07:30' THEN mistni::date + time '07:30'
                 WHEN mistni::time <= time '16:30' THEN mistni::date + time '16:30'
                 ELSE (mistni::date + 1) + time '07:30' END) AT TIME ZONE 'Europe/Prague';
END $$;

CREATE OR REPLACE FUNCTION polarita.test_navrh(klic uuid, spis text, verze bigint, novy_stav text, rada text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE pripad polarita.test_spis; zadost polarita.test_rozhodnuti; cas timestamptz := statement_timestamp();
BEGIN
    IF klic IS NULL OR spis IS NULL OR verze IS NULL OR novy_stav IS NULL OR rada IS NULL THEN
        RAISE EXCEPTION 'Neúplný návrh';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(klic::text, 17));
    SELECT * INTO zadost FROM polarita.test_rozhodnuti WHERE id = klic;
    IF FOUND THEN
        IF (zadost.cislo, zadost.verze_pred, zadost.po, zadost.fronta)
            IS DISTINCT FROM (spis, verze, novy_stav, rada) THEN
            RAISE EXCEPTION 'Identifikátor patří jinému návrhu';
        END IF;
        RETURN klic;
    END IF;
    SELECT * INTO STRICT pripad FROM polarita.test_spis WHERE cislo = spis FOR SHARE;
    IF pripad.verze <> verze THEN RAISE EXCEPTION 'Verze spisu se změnila' USING ERRCODE='40001'; END IF;
    INSERT INTO polarita.test_rozhodnuti(id, cislo, verze_pred, pred, po, fronta, vytvoreno, dostupne)
        VALUES (klic, spis, verze, pripad.stav, novy_stav, rada, cas, polarita.test_okno(cas, rada));
    RETURN klic;
END $$;

CREATE OR REPLACE FUNCTION polarita.test_rozhodni(klic uuid, volba text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE zadost polarita.test_rozhodnuti;
BEGIN
    IF volba IS NULL OR volba NOT IN ('mutation_confirm','mutation_cancel') THEN
        RAISE EXCEPTION 'Neznámá akce';
    END IF;
    SELECT * INTO STRICT zadost FROM polarita.test_rozhodnuti WHERE id = klic FOR UPDATE;
    IF zadost.akce = volba THEN RETURN volba; END IF;
    IF zadost.akce IS NOT NULL THEN RAISE EXCEPTION 'Položka je již vyřízená'; END IF;
    IF statement_timestamp() < zadost.dostupne THEN RAISE EXCEPTION 'Denní dávka ještě není otevřená'; END IF;
    IF volba = 'mutation_confirm' THEN
        UPDATE polarita.test_spis SET stav = zadost.po, verze = verze + 1
            WHERE cislo = zadost.cislo AND verze = zadost.verze_pred AND stav = zadost.pred;
        IF NOT FOUND THEN RAISE EXCEPTION 'Verze spisu se změnila' USING ERRCODE='40001'; END IF;
    END IF;
    UPDATE polarita.test_rozhodnuti SET akce = volba, rozhodnuto = statement_timestamp() WHERE id = klic;
    RETURN volba;
END $$;

REVOKE ALL ON FUNCTION polarita.test_okno(timestamptz,text), polarita.test_navrh(uuid,text,bigint,text,text),
    polarita.test_rozhodni(uuid,text) FROM PUBLIC;
GRANT SELECT ON polarita.test_spis, polarita.test_rozhodnuti TO pol_decisions_reviewer, pol_decisions_proposer;
GRANT EXECUTE ON FUNCTION polarita.test_navrh(uuid,text,bigint,text,text) TO pol_decisions_proposer;
GRANT EXECUTE ON FUNCTION polarita.test_rozhodni(uuid,text) TO pol_decisions_reviewer;
RESET ROLE;
REVOKE CREATE ON SCHEMA polarita FROM pol_decisions_owner;
COMMIT;
