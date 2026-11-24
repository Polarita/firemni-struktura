\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('polarita.den-1-test'));
CREATE SCHEMA IF NOT EXISTS polarita_test_lhutnik;
REVOKE ALL ON SCHEMA polarita_test_lhutnik FROM PUBLIC;
CREATE TABLE IF NOT EXISTS polarita_test_lhutnik.kontroly (
    kod text PRIMARY KEY,
    popis text NOT NULL,
    role text NOT NULL CHECK (role ~ '^[0-9]{5}$'),
    opakovani interval NOT NULL CHECK (opakovani > interval '0'),
    posledni_kontrola date NOT NULL,
    cesta_vault text NOT NULL
);
REVOKE ALL ON polarita_test_lhutnik.kontroly FROM PUBLIC;
CREATE TEMP TABLE ocekavane (LIKE polarita_test_lhutnik.kontroly INCLUDING ALL) ON COMMIT DROP;
INSERT INTO ocekavane VALUES
    ('TEST-D1-PREDPIS', 'Bibliografický záznam předpisu', '15001', '1 week', '2026-11-24', '04-Pravo-a-Smlouvy/den-1-registr-zdroje.md'),
    ('TEST-D1-NORMY', 'Metodiky a nové edice norem', '15002', '1 month', '2026-11-24', '03-Normy-a-Metodiky/den-1-metodika.md'),
    ('TEST-D1-SMLOUVY', 'Smlouvy, směrnice a informační doložky', '15001', '1 year', '2026-11-24', '04-Pravo-a-Smlouvy/den-1-pravni-minimum.md'),
    ('TEST-D1-LIMITY', 'Shoda výchozích lhůt a limitů se záznamy', '15001', '1 year', '2026-11-24', '04-Pravo-a-Smlouvy/den-1-pravni-minimum.md'),
    ('TEST-D1-STARI', 'Úplnost a stáří záznamů v bázi', '17004', '1 month', '2026-11-24', '04-Pravo-a-Smlouvy/den-1-pravni-minimum.md');
INSERT INTO polarita_test_lhutnik.kontroly SELECT * FROM ocekavane ON CONFLICT (kod) DO NOTHING;
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM ocekavane o JOIN polarita_test_lhutnik.kontroly k USING (kod)
        WHERE (k.popis,k.role,k.opakovani,k.cesta_vault) IS DISTINCT FROM (o.popis,o.role,o.opakovani,o.cesta_vault)
    ) THEN RAISE EXCEPTION 'Kolize zkušebních úloh Dne 1'; END IF;
END $$;
CREATE OR REPLACE VIEW polarita_test_lhutnik.plan AS
SELECT kod,popis,role,cesta_vault,posledni_kontrola,
       (posledni_kontrola + opakovani)::date AS pristi_kontrola,
       CURRENT_DATE > (posledni_kontrola + opakovani)::date AS po_lhute
FROM polarita_test_lhutnik.kontroly;
GRANT USAGE ON SCHEMA polarita_test_lhutnik TO pol_vault_read;
GRANT SELECT ON polarita_test_lhutnik.plan TO pol_vault_read;
SET LOCAL ROLE pol_vault_read;
SELECT kod, pristi_kontrola, po_lhute FROM polarita_test_lhutnik.plan WHERE kod LIKE 'TEST-D1-%' ORDER BY kod;
COMMIT;
