-- Oddělená transakce se vzorovým rozváděčem a smlouvou velkoobchodu.
BEGIN;
SELECT gen_random_uuid() AS zar,gen_random_uuid() AS kus,gen_random_uuid() AS pohyb \gset
SELECT set_config('polarita.test_kus', :'kus', true),set_config('polarita.test_pohyb', :'pohyb', true) \g /dev/null
SET LOCAL ROLE pol_wms_ddl;
INSERT INTO wms.zaruky_kusu VALUES (:'zar','Velkoobchod TEST','Výroba TEST',:'kus','TEST-R1','novy_rozvadec',
    daterange(current_date-1,current_date+10),repeat('1',64));
SET LOCAL ROLE db_eshop;
DO $d$
DECLARE k uuid:=current_setting('polarita.test_kus')::uuid;
BEGIN
    BEGIN PERFORM wms.prijmi_sken(k,'Výroba TEST','CHYBNÝ SKEN','TEST-R1','MAIN-101'); RAISE EXCEPTION 'Příjem bez párování';
    EXCEPTION WHEN no_data_found THEN NULL; END;
END $d$;
SET LOCAL ROLE pol_wms_ddl;
UPDATE wms.zaruky_kusu SET platnost=daterange(current_date-10,current_date-2) WHERE id=:'zar';
SET LOCAL ROLE db_eshop;
DO $d$
DECLARE k uuid:=current_setting('polarita.test_kus')::uuid;
BEGIN
    BEGIN PERFORM wms.prijmi_sken(k,'Výroba TEST',k::text,'TEST-R1','MAIN-101'); RAISE EXCEPTION 'Příjem s neplatnou zárukou';
    EXCEPTION WHEN SQLSTATE 'P1002' THEN NULL; END;
END $d$;
SET LOCAL ROLE pol_wms_ddl;
UPDATE wms.zaruky_kusu SET platnost=daterange(current_date-1,current_date+10) WHERE id=:'zar';
SET LOCAL ROLE db_eshop;
SELECT wms.prijmi_sken(:'kus','Výroba TEST',:'kus','TEST-R1','MAIN-101') \g /dev/null
SELECT wms.prijmi_sken(:'kus','Výroba TEST',:'kus','TEST-R1','MAIN-101') \g /dev/null
DO $d$
DECLARE k uuid:=current_setting('polarita.test_kus')::uuid; v uuid:=current_setting('polarita.test_pohyb')::uuid;
BEGIN
    BEGIN PERFORM wms.vydej_sken(v,k,'Výroba TEST','CHYBNÝ SKEN','MAIN-101','POL-2026-99107'); RAISE EXCEPTION 'Prošel cizí sken';
    EXCEPTION WHEN no_data_found THEN NULL; END;
    BEGIN PERFORM wms.vydej_sken(v,k,'Výroba TEST',k::text,'MAIN-101','POL-2026-99107'); RAISE EXCEPTION 'Prošel nedoložený rozváděč';
    EXCEPTION WHEN SQLSTATE 'P1003' THEN NULL; END;
    BEGIN INSERT INTO wms.doklady_rozvadece VALUES(k,'stitek_ce',111,repeat('2',64)); RAISE EXCEPTION 'Sklad přidal vlastní doklad';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $d$;
SET LOCAL ROLE pol_wms_ddl;
INSERT INTO wms.doklady_rozvadece VALUES (:'kus','vyrobni_pas',111,repeat('2',64));
SET LOCAL ROLE db_eshop;
DO $d$
DECLARE k uuid:=current_setting('polarita.test_kus')::uuid; v uuid:=current_setting('polarita.test_pohyb')::uuid;
BEGIN
    BEGIN PERFORM wms.vydej_sken(v,k,'Výroba TEST',k::text,'MAIN-101','POL-2026-99107'); RAISE EXCEPTION 'Prošel kus bez CE';
    EXCEPTION WHEN SQLSTATE 'P1003' THEN NULL; END;
END $d$;
SET LOCAL ROLE pol_wms_ddl;
INSERT INTO wms.doklady_rozvadece VALUES (:'kus','stitek_ce',112,repeat('3',64));
UPDATE wms.zaruky_kusu SET platnost=daterange(current_date-10,current_date-2) WHERE id=:'zar';
SET LOCAL ROLE db_eshop;
DO $d$
DECLARE k uuid:=current_setting('polarita.test_kus')::uuid; v uuid:=current_setting('polarita.test_pohyb')::uuid;
BEGIN
    BEGIN PERFORM wms.vydej_sken(v,k,'Výroba TEST',k::text,'MAIN-101','POL-2026-99107'); RAISE EXCEPTION 'Prošla již neplatná záruka';
    EXCEPTION WHEN SQLSTATE 'P1002' THEN NULL; END;
END $d$;
SET LOCAL ROLE pol_wms_ddl;
UPDATE wms.zaruky_kusu SET platnost=daterange(current_date-2,current_date+10) WHERE id=:'zar';
SET LOCAL ROLE db_eshop;
SELECT wms.vydej_sken(:'pohyb',:'kus','Výroba TEST',:'kus','MAIN-101','POL-2026-99107') \g /dev/null
SELECT wms.vydej_sken(:'pohyb',:'kus','Výroba TEST',:'kus','MAIN-101','POL-2026-99107') \g /dev/null
DO $d$
DECLARE k uuid:=current_setting('polarita.test_kus')::uuid; v uuid:=current_setting('polarita.test_pohyb')::uuid;
BEGIN
    BEGIN PERFORM wms.vydej_sken(v,k,'Výroba TEST',k::text,'MAIN-101','POL-2026-99108'); RAISE EXCEPTION 'Prošel opakovaný výdej jiné stavbě';
    EXCEPTION WHEN unique_violation THEN NULL; END;
    IF (SELECT count(*) FROM wms.serie_prehled WHERE id=k AND vydej=v AND vyrobni_pas AND stitek_ce AND spis='POL-2026-99107')<>1
    THEN RAISE EXCEPTION 'Chybí jednoznačný doklad o výdeji'; END IF;
END $d$;
ROLLBACK;
