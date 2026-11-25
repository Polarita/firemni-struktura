\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.ciselne_rady_test',0));
-- Obě starší řady si ponechají původní tabulku, zámky i vazby vystavených čísel.
GRANT USAGE ON SCHEMA polarita_registr_test TO pol_metadata_api,pol_metadata_read,pol_metadata_ddl;
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_constraint WHERE conname='doklad_spis_fk'
                   AND conrelid='polarita_registr_test.doklad'::regclass) THEN
        ALTER TABLE polarita_registr_test.doklad ADD CONSTRAINT doklad_spis_fk
            FOREIGN KEY(spis) REFERENCES polarita_test_spisy.spis(pozadavek);
    END IF;
END $$;
CREATE OR REPLACE FUNCTION polarita_registr_test.zaloz_spis(klic uuid,pobocka integer)
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path=pg_catalog,pg_temp
AS 'SELECT polarita_test_spisy.zaloz(klic,pobocka)';
CREATE OR REPLACE FUNCTION polarita_registr_test.pridel_rozvadec(klic uuid,spis uuid,oznaceni text)
RETURNS text LANGUAGE sql SECURITY INVOKER SET search_path=pg_catalog,pg_temp
AS 'SELECT polarita_test_spisy.pridel_vyrobni_cislo(klic,spis,oznaceni)';
REVOKE ALL ON FUNCTION polarita_registr_test.zaloz_spis(uuid,integer),
    polarita_registr_test.pridel_rozvadec(uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION polarita_registr_test.zaloz_spis(uuid,integer) TO pol_metadata_api;
GRANT EXECUTE ON FUNCTION polarita_registr_test.pridel_rozvadec(uuid,uuid,text) TO pol_metadata_ddl;
CREATE OR REPLACE VIEW polarita_registr_test.prehled_dokladu AS
    SELECT s.case_id, d.cislo, d.druh, d.podklad_sha256 FROM polarita_registr_test.doklad d
    JOIN polarita_test_spisy.karty s ON s.pozadavek=d.spis;
GRANT SELECT ON polarita_registr_test.prehled_dokladu TO pol_metadata_api,pol_metadata_read;
COMMIT;
