\set ON_ERROR_STOP on
BEGIN;
DO $test$
DECLARE
    kod text := polarita_test_spisy.zaloz(gen_random_uuid(),101)->>'case_id';
    cizi text := polarita_test_spisy.zaloz(gen_random_uuid(),101)->>'case_id';
    id uuid := gen_random_uuid();
    otisk text := repeat('1',64);
    dnes date := (now() AT TIME ZONE 'Europe/Prague')::date;
    vysledek text;
BEGIN
    PERFORM polarita_test_spisy.prijmi_sanon(kod,id,otisk,42);
    IF polarita_test_spisy.zapis_revizi(kod,'TEST','R1',id,dnes-3,dnes,dnes+1) <> 'doklad'
    THEN RAISE EXCEPTION 'Přijata příloha v karanténě'; END IF;
    IF NOT polarita_test_spisy.uzavri_ocr(id,kod,otisk,repeat('2',64),1,'ocr-hotovo')
    THEN RAISE EXCEPTION 'Chybná příprava testovacích dat'; END IF;
    IF polarita_test_spisy.zapis_revizi(cizi,'TEST','R1',id,dnes-3,dnes,dnes+1) <> 'doklad'
       OR polarita_test_spisy.zapis_revizi(kod,'TEST','R1',id,dnes+1,dnes+2,dnes+3) <> 'datum'
       OR polarita_test_spisy.zapis_revizi(kod,'TEST','R1',id,dnes-3,dnes+2,dnes+1) <> 'datum'
    THEN RAISE EXCEPTION 'Přijaty chybné údaje'; END IF;
    FOR i IN 1..2 LOOP
        IF polarita_test_spisy.zapis_revizi(kod,'TEST','R1',id,dnes-3,dnes,dnes) <> 'ulozeno'
        THEN RAISE EXCEPTION 'Nepodařilo se opakovat zápis'; END IF;
    END LOOP;
    IF polarita_test_spisy.zapis_revizi(kod,'TEST','R1',id,dnes-3,dnes,dnes+5) <> 'kolize'
    THEN RAISE EXCEPTION 'Změna zapsané revize'; END IF;
    PERFORM polarita_test_spisy.zapis_revizi(kod,'TEST','R2',id,dnes-3,dnes-2,dnes-1);
    PERFORM polarita_test_spisy.zapis_revizi(kod,'TEST','R3',id,dnes-3,dnes+2,dnes+3);
    PERFORM polarita_test_spisy.zapis_revizi(kod,'TEST','R3',id,dnes-6,dnes-5,dnes-4);
    SELECT string_agg(stav,',' ORDER BY zarizeni) INTO vysledek FROM polarita_test_spisy.kniha_objektu WHERE case_id=kod;
    IF vysledek IS DISTINCT FROM 'blizi-se,po-lhute,ve-lhute' THEN RAISE EXCEPTION 'Chybný semafor %',vysledek; END IF;
    IF (SELECT count(*) FROM polarita_test_spisy.casova_osa WHERE case_id=kod) <> 7
       OR (SELECT count(*) FROM polarita_test_spisy.casova_osa WHERE case_id=cizi) <> 1
    THEN RAISE EXCEPTION 'Ztracená nebo cizí událost na kartě'; END IF;
    SELECT pozice INTO STRICT vysledek FROM polarita_test_spisy.casova_osa WHERE case_id=kod AND druh='ocr-hotovo';
    PERFORM polarita_test_spisy.uzavri_ocr(id,kod,otisk,repeat('2',64),1,'ocr-hotovo');
    IF NOT EXISTS (SELECT FROM polarita_test_spisy.casova_osa WHERE case_id=kod AND druh='ocr-hotovo' AND pozice=vysledek)
    THEN RAISE EXCEPTION 'Opakované OCR přepsalo čas dokončení'; END IF;
    -- Starší archivované přílohy nemají zaznamenaný čas dokončení.
    UPDATE polarita_test_spisy.prijem_sanonu SET uzavreno=NULL WHERE priloha=id;
    PERFORM polarita_test_spisy.uzavri_ocr(id,kod,otisk,repeat('2',64),1,'ocr-hotovo');
    IF EXISTS (SELECT FROM polarita_test_spisy.casova_osa WHERE case_id=kod AND druh='ocr-hotovo')
    THEN RAISE EXCEPTION 'Smyšlený čas historické události'; END IF;
    -- Jeden okamžik převzetí může mít i více příloh, než se vejde na stránku.
    INSERT INTO polarita_test_spisy.prijem_sanonu(priloha,spis,otisk,bajtu,prijato)
    SELECT gen_random_uuid(),k.pozadavek,repeat('1',64),42,now() + interval '1 day'
    FROM polarita_test_spisy.karty k CROSS JOIN generate_series(1,27) WHERE k.case_id=kod;
    SELECT pozice INTO STRICT vysledek FROM polarita_test_spisy.casova_osa
        WHERE case_id=kod ORDER BY pozice DESC LIMIT 1 OFFSET 19;
    IF (SELECT count(DISTINCT pozice) FROM polarita_test_spisy.casova_osa WHERE case_id=kod AND pozice < vysledek) <> 13
    THEN RAISE EXCEPTION 'Ztracené souběžné události při stránkování'; END IF;
    IF NOT has_table_privilege('pol_metadata_api','polarita_test_spisy.casova_osa','SELECT')
       OR has_table_privilege('pol_metadata_api','polarita_test_spisy.casova_osa','INSERT')
    THEN RAISE EXCEPTION 'Chybná oprávnění časové osy'; END IF;
    IF has_function_privilege('pol_metadata_read','polarita_test_spisy.zapis_revizi(text,text,text,uuid,date,date,date)','EXECUTE')
       OR has_table_privilege('pol_metadata_api','polarita_test_spisy.revize_objektu','UPDATE')
    THEN RAISE EXCEPTION 'Nadměrná oprávnění'; END IF;
END $test$;
ROLLBACK;
