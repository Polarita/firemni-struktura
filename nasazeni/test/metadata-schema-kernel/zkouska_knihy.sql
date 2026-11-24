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
    IF has_function_privilege('pol_metadata_read','polarita_test_spisy.zapis_revizi(text,text,text,uuid,date,date,date)','EXECUTE')
       OR has_table_privilege('pol_metadata_api','polarita_test_spisy.revize_objektu','UPDATE')
    THEN RAISE EXCEPTION 'Nadměrná oprávnění'; END IF;
END $test$;
ROLLBACK;
