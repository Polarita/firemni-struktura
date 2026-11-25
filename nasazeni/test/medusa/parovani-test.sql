BEGIN;
SELECT gen_random_uuid() AS o,gen_random_uuid() AS dl1,gen_random_uuid() AS dl2,
       gen_random_uuid() AS dl3,gen_random_uuid() AS fa,gen_random_uuid() AS dalsi,
       gen_random_uuid() AS prijem,gen_random_uuid() AS zbytek \gset
SELECT set_config('polarita.test_objednavka',:'o',true) \g /dev/null
CREATE FUNCTION pg_temp.odmitni(stav text,pohyb uuid,o uuid,doklady uuid[]) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        PERFORM wms.potvrd_nakup(pohyb,o,doklady);
    EXCEPTION WHEN OTHERS THEN
        IF SQLSTATE=stav THEN RETURN; END IF;
        RAISE;
    END;
    RAISE EXCEPTION 'Příjem měl vrátit chybu %',stav;
END $$;

SET LOCAL ROLE pol_wms_objednavky;
INSERT INTO wms.nakupni_objednavky(id,subjekt,dodavatel,cislo,radek,cil,varianta,jednotka,mnozstvi,mena,cena_bez_phe,phe_za_jednotku,otisk_sha256)
VALUES (:'o','Polarita TEST','Dodavatel TEST',:'o',1,'POL-2026-99108','LED-TEST','ks',10,'CZK',80,2,repeat('1',64));

SET LOCAL ROLE db_eshop;
INSERT INTO wms.skladove_prijemky(id,subjekt,dodavatel,cislo,radek,polozka_objednavky,cil,varianta,jednotka,mnozstvi,sklad,otisk_sha256)
SELECT id,'Polarita TEST','Dodavatel TEST',id::text,1,:'o','POL-2026-99108','LED-TEST','ks',kusy,'MAIN-101',repeat('2',64)
FROM (VALUES (:'dl1'::uuid,2),(:'dl2'::uuid,4),(:'dl3'::uuid,4)) AS r(id,kusy);
DO $$
BEGIN
    IF has_table_privilege(current_user,'wms.nakupni_objednavky','INSERT')
        OR has_table_privilege(current_user,'wms.nakupni_faktury','INSERT')
        OR has_table_privilege(current_user,'wms.nakupni_prijmy','INSERT')
    THEN RAISE EXCEPTION 'Sklad smí sám vytvořit účetní nebo nákupní podklad'; END IF;
END $$;
SET LOCAL ROLE pol_wms_faktury;
INSERT INTO wms.nakupni_faktury(id,subjekt,dodavatel,cislo,radek,polozka_objednavky,cil,varianta,jednotka,mnozstvi,mena,cena_bez_phe,phe_za_jednotku,otisk_sha256)
SELECT id,'Polarita TEST','Dodavatel TEST',id::text,1,:'o','POL-2026-99108','LED-TEST','ks',kusy,'CZK',80,2,repeat('3',64)
FROM (VALUES (:'fa'::uuid,6),(:'dalsi'::uuid,4)) AS f(id,kusy);

SET LOCAL ROLE db_eshop;
SELECT pg_temp.odmitni('P1004',:'prijem',:'o',ARRAY[:'dl1']::uuid[]) \g /dev/null
SELECT pg_temp.odmitni('P1004',:'prijem',:'o',ARRAY[:'dl1',:'fa']::uuid[]) \g /dev/null
SELECT pg_temp.odmitni('22023',:'prijem',:'o',ARRAY[:'dl1',:'dl1',:'fa']::uuid[]) \g /dev/null
SELECT pg_temp.odmitni('P1004',:'prijem',:'o',ARRAY[:'dl1',:'dl2',gen_random_uuid()::text]::uuid[]) \g /dev/null
-- Změna jednoho pole z jinak shodné faktury musí příjem zastavit a zanechat stav nezměněný.
SET LOCAL ROLE pol_wms_ddl;
DO $$
DECLARE
    o uuid:=current_setting('polarita.test_objednavka')::uuid;
    f uuid; dl uuid; sloupec text; hodnota text;
BEGIN
    SELECT id INTO STRICT f FROM wms.nakupni_doklady WHERE polozka_objednavky=o AND druh='faktura' AND mnozstvi=4;
    SELECT id INTO dl FROM wms.nakupni_doklady WHERE polozka_objednavky=o AND druh='prijemka' AND mnozstvi=4 LIMIT 1;
    FOR sloupec,hodnota IN VALUES ('subjekt','Jiný odběratel'),('dodavatel','Jiný dodavatel'),('cil','VAN-101-02'),
            ('varianta','LED-JINA'),('jednotka','bal'),('mena','EUR'),('cena_bez_phe','81'),('phe_za_jednotku','0')
    LOOP
        BEGIN
            EXECUTE format('UPDATE wms.nakupni_doklady SET %I=%L WHERE id=$1',sloupec,hodnota) USING f;
            PERFORM pg_temp.odmitni('P1004',gen_random_uuid(),o,ARRAY[dl,f]);
            RAISE EXCEPTION USING ERRCODE='Z0001';
        EXCEPTION WHEN SQLSTATE 'Z0001' THEN NULL; END;
    END LOOP;
    IF EXISTS (SELECT FROM wms.nakupni_prijmy WHERE objednavka=o) THEN RAISE EXCEPTION 'Neshoda připsala materiál'; END IF;
END $$;

SET LOCAL ROLE db_eshop;
SELECT wms.potvrd_nakup(:'prijem',:'o',ARRAY[:'dl1',:'dl2',:'fa']::uuid[]) \g /dev/null
SELECT wms.potvrd_nakup(:'prijem',:'o',ARRAY[:'fa',:'dl2',:'dl1']::uuid[]) \g /dev/null
SELECT pg_temp.odmitni('23505',gen_random_uuid(),:'o',ARRAY[:'dl1',:'dl2',:'fa']::uuid[]) \g /dev/null
SELECT pg_temp.odmitni('23505',:'prijem',:'o',ARRAY[:'dl3',:'dalsi']::uuid[]) \g /dev/null
SET LOCAL ROLE pol_wms_ddl;
UPDATE wms.nakupni_doklady SET mnozstvi=9 WHERE id=:'o';
SET LOCAL ROLE db_eshop;
SELECT pg_temp.odmitni('P1004',:'zbytek',:'o',ARRAY[:'dl3',:'dalsi']::uuid[]) \g /dev/null
SET LOCAL ROLE pol_wms_ddl;
UPDATE wms.nakupni_doklady SET mnozstvi=10 WHERE id=:'o';
SET LOCAL ROLE db_eshop;
SELECT wms.potvrd_nakup(:'zbytek',:'o',ARRAY[:'dl3',:'dalsi']::uuid[]) \g /dev/null
DO $$
BEGIN
    IF (SELECT (sum(mnozstvi),count(*),count(DISTINCT prijem)) IS DISTINCT FROM (10::numeric,3::bigint,2::bigint)
        FROM wms.prijaty_material WHERE objednavka=current_setting('polarita.test_objednavka')::uuid)
    THEN RAISE EXCEPTION 'Chybí dílčí dodávky nebo se příjem zdvojil'; END IF;
END $$;
ROLLBACK;
