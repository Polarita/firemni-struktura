BEGIN;
SET LOCAL TIME ZONE 'Europe/Prague';
-- Ověř šifrování a databázové role na dočasných záznamech oddělených od případných existujících zkoušek.
SELECT gen_random_uuid() AS osoba, gen_random_uuid() AS vedouci, gen_random_uuid() AS bez_archivu \gset
SELECT set_config('polarita.zkousena_osoba', :'osoba', true) IS NOT NULL,
       set_config('polarita.zkouseny_vedouci', :'vedouci', true) IS NOT NULL,
       set_config('polarita.bez_archivu', :'bez_archivu', true) IS NOT NULL;
SET LOCAL ROLE db_gdpr_zkousky;
DO $$
DECLARE
    osoba uuid := current_setting('polarita.zkousena_osoba')::uuid;
    komise uuid[] := ARRAY[gen_random_uuid(), gen_random_uuid(), gen_random_uuid()];
    klic text := encode(gen_random_bytes(32),'hex');
    sifra bytea := pgp_sym_encrypt('Fiktivní účastník TEST', klic, 'cipher-algo=aes256');
    otisk bytea := digest('Obsah cvičného protokolu','sha256');
BEGIN
    INSERT INTO akademie_test.protokol VALUES
        (gen_random_uuid(), osoba,'pouceni',now()-interval '1 day',current_date+10,true,'{}',sifra,otisk),
        (gen_random_uuid(), osoba,'elektrotechnik',now()-interval '2 days',current_date+10,true,komise,sifra,otisk),
        (gen_random_uuid(), osoba,'elektrotechnik',now()-interval '1 day',current_date+10,false,komise,sifra,otisk),
        (gen_random_uuid(), current_setting('polarita.zkouseny_vedouci')::uuid,'vedouci',now()-interval '10 days',current_date-1,true,komise,sifra,otisk),
        (gen_random_uuid(), current_setting('polarita.bez_archivu')::uuid,'vedouci',now(),current_date+10,true,komise,sifra,NULL);
    IF (SELECT pgp_sym_decrypt(sifrovany_obsah,klic) FROM akademie_test.protokol WHERE person_no=osoba AND druh='pouceni')
       IS DISTINCT FROM 'Fiktivní účastník TEST' THEN RAISE EXCEPTION 'Chyba šifrování vzoru'; END IF;
    BEGIN
        INSERT INTO akademie_test.protokol VALUES (gen_random_uuid(),osoba,'vedouci',now(),current_date+10,true,
            ARRAY[komise[1],komise[1],komise[2]],sifra,otisk);
        RAISE EXCEPTION 'Duplicitní člen komise prošel';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO akademie_test.protokol VALUES (gen_random_uuid(),osoba,'pouceni',now(),current_date+1500,true,'{}',sifra,otisk);
        RAISE EXCEPTION 'Neplatná doba opakování prošla';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END $$;
SET LOCAL ROLE polarita_ai_masked;
DO $$
DECLARE
    osoba uuid := current_setting('polarita.zkousena_osoba')::uuid;
    pohled text;
BEGIN
    IF (SELECT zpusobily FROM akademie_prehled_test.pouceni WHERE person_no=osoba) IS DISTINCT FROM true
       OR (SELECT zpusobily FROM akademie_prehled_test.elektrotechnik WHERE person_no=osoba) IS DISTINCT FROM false
       OR (SELECT zpusobily FROM akademie_prehled_test.vedouci WHERE person_no=current_setting('polarita.zkouseny_vedouci')::uuid) IS DISTINCT FROM false
       OR EXISTS (SELECT FROM akademie_prehled_test.vedouci WHERE person_no=current_setting('polarita.bez_archivu')::uuid)
       THEN RAISE EXCEPTION 'Nesouhlasí oddělení výsledků, platnost nebo archivace'; END IF;
    FOREACH pohled IN ARRAY ARRAY['pouceni','elektrotechnik','vedouci'] LOOP
        IF (SELECT array_agg(column_name::text || ':' || data_type ORDER BY ordinal_position) FROM information_schema.columns
            WHERE table_schema='akademie_prehled_test' AND table_name=pohled)
            IS DISTINCT FROM ARRAY['person_no:uuid','zpusobily:boolean'] THEN RAISE EXCEPTION 'Pohled promítá jiné sloupce'; END IF;
    END LOOP;
    BEGIN
        PERFORM sifrovany_obsah FROM akademie_test.protokol LIMIT 1;
        RAISE EXCEPTION 'Role ai přečetla zdrojové záznamy';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    IF has_table_privilege(current_user, 'akademie_prehled_test.pouceni', 'INSERT,UPDATE,DELETE')
       OR has_schema_privilege(current_user, 'akademie_prehled_test', 'CREATE') THEN
        RAISE EXCEPTION 'Role ai má práva ke změně přehledu';
    END IF;
END $$;
ROLLBACK;
