\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.provizni_ledger_test', 0)) AS zamknuto \gset
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pol_provize_zapis') THEN
        CREATE ROLE pol_provize_zapis NOLOGIN;
    END IF;
END $$;
SET LOCAL ROLE pol_registr_ddl;
CREATE TABLE IF NOT EXISTS polarita_registr_test.provizni_ledger (
    druh text NOT NULL CHECK (druh IN ('realizace', 'mrr')),
    zdroj text NOT NULL,
    udalost text NOT NULL,
    doklad text NOT NULL,
    partner text NOT NULL,
    obdobi date NOT NULL CHECK (extract(day FROM obdobi) = 1),
    zaklad numeric(16,2) NOT NULL CHECK (zaklad <> 0 AND zaklad <> 'NaN'::numeric),
    sazba numeric(5,2) NOT NULL,
    provize numeric(16,2) NOT NULL CHECK (provize = round(zaklad * sazba / 100, 2)),
    PRIMARY KEY (druh, zdroj, udalost),
    CHECK ((druh = 'realizace' AND sazba = 100 AND zaklad > 0)
        OR (druh = 'mrr' AND sazba BETWEEN 10 AND 15))
);
GRANT USAGE ON SCHEMA polarita_registr_test TO pol_provize_zapis;
GRANT INSERT, SELECT ON polarita_registr_test.provizni_ledger TO pol_provize_zapis;
RESET ROLE;
CREATE TEMP TABLE prijem_provizi (LIKE polarita_registr_test.provizni_ledger INCLUDING ALL)
    ON COMMIT DROP;
INSERT INTO prijem_provizi
SELECT * FROM jsonb_populate_recordset(NULL::polarita_registr_test.provizni_ledger, :'polozky'::jsonb);
GRANT SELECT ON TABLE prijem_provizi TO pol_provize_zapis;
SET LOCAL ROLE pol_provize_zapis;
INSERT INTO polarita_registr_test.provizni_ledger
SELECT * FROM prijem_provizi
ON CONFLICT (druh, zdroj, udalost) DO NOTHING;
DO $$
BEGIN
    IF EXISTS (SELECT * FROM prijem_provizi EXCEPT SELECT * FROM polarita_registr_test.provizni_ledger) THEN
        RAISE EXCEPTION 'Změněná data pod již zaúčtovanou událostí.' USING ERRCODE = 'PZ001';
    END IF;
    IF has_table_privilege(current_user,'polarita_registr_test.provizni_ledger','UPDATE,DELETE,TRUNCATE') THEN
        RAISE EXCEPTION 'Zapisovací role může změnit historii provizí.';
    END IF;
END $$;
SELECT druh || ' · ' || doklad || ' · ' || partner || ' · ' || provize || ' CZK'
FROM polarita_registr_test.provizni_ledger JOIN prijem_provizi USING
    (druh, zdroj, udalost, doklad, partner, obdobi, zaklad, sazba, provize)
ORDER BY druh, doklad;
COMMIT;
