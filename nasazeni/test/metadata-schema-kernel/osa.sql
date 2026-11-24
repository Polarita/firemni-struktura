\set ON_ERROR_STOP on
BEGIN;
SET LOCAL ROLE pol_metadata_ddl;
CREATE INDEX IF NOT EXISTS prijem_sanonu_spis_idx ON polarita_test_spisy.prijem_sanonu (spis);
CREATE OR REPLACE VIEW polarita_test_spisy.casova_osa AS
WITH udalosti(spis,cas,klic,druh,popis,dokument) AS (
    SELECT pozadavek,zalozeno,'1','spis','Založen spis pro pobočku ' || branch_id,NULL::bigint
    FROM polarita_test_spisy.spis
    UNION ALL
    SELECT spis,prijato,'2.' || priloha,'prijem','Převzato PDF do karantény · ' || bajtu || ' B',NULL
    FROM polarita_test_spisy.prijem_sanonu
    UNION ALL
    SELECT spis,uzavreno,'3.' || priloha,stav,
       CASE stav WHEN 'odmitnuto' THEN 'Karanténa odmítla přílohu'
                 WHEN 'ocr-hotovo' THEN 'Dokument archivován, OCR dokončeno'
                 WHEN 'ke-kontrole' THEN 'Dokument archivován, OCR vyžaduje kontrolu' END,dokument
    FROM polarita_test_spisy.prijem_sanonu WHERE uzavreno IS NOT NULL
    UNION ALL
    SELECT r.spis,r.zapsano,'4.' || r.objekt || '.' || r.zarizeni || '.' || to_char(r.revize,'YYYY-MM-DD'),
           'revize','Zapsána revize · ' || r.objekt || ' / ' || r.zarizeni || ' · provedena ' || to_char(r.revize,'DD.MM.YYYY'),p.dokument
    FROM polarita_test_spisy.revize_objektu r
    JOIN polarita_test_spisy.prijem_sanonu p ON (p.spis,p.priloha)=(r.spis,r.priloha)
)
SELECT k.case_id,u.cas,u.druh,u.popis,u.dokument,
       (to_char(u.cas AT TIME ZONE 'UTC','YYYYMMDDHH24MISSUS') || '.' || u.klic) COLLATE "C" AS pozice
FROM udalosti u JOIN polarita_test_spisy.karty k ON k.pozadavek=u.spis;
GRANT SELECT ON polarita_test_spisy.casova_osa TO pol_metadata_api,pol_metadata_read;
COMMIT;
