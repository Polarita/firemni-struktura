-- Běžná rozpočtová kontrola v nativní DB pod vyhrazenými rolemi. Všechny rezervace zkoušky vrací rollback.
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('polarita.finops.vydaj',0));
SET LOCAL ROLE pol_finops_read;
DO $$ DECLARE s jsonb := polarita_finops.stav(); BEGIN
    IF jsonb_array_length(s->'pozice')<>20 OR (s->>'strop_cent')::integer<>47000 THEN RAISE EXCEPTION 'Neshoda živých kvót'; END IF;
    IF has_table_privilege(current_user,'polarita_finops.volani','INSERT') OR
       has_function_privilege(current_user,'polarita_finops.rezervuj(uuid,text,uuid,text,integer,uuid)','EXECUTE')
    THEN RAISE EXCEPTION 'Čtenář smí zapisovat'; END IF;
END $$;
RESET ROLE;
SET LOCAL ROLE pol_finops_call;
DO $$
DECLARE k uuid:=gen_random_uuid(); t uuid:=gen_random_uuid(); j uuid:=gen_random_uuid(); c text;
BEGIN
    IF has_function_privilege(current_user,'polarita_finops.uvolni(uuid,uuid,text,uuid,integer)','EXECUTE')
    THEN RAISE EXCEPTION 'Volající může sám uvolnit P1'; END IF;
    c:=polarita_finops.rezervuj(k,'11001',t,'provoz',2975);
    IF c<>'BUDGET_OK' THEN RAISE EXCEPTION 'Testovací kvóta není volná: %',c; END IF;
    IF polarita_finops.rezervuj(k,'11001',t,'provoz',2975)<>'OPAKOVANI' THEN RAISE EXCEPTION 'Opakování'; END IF;
    IF polarita_finops.rezervuj(j,'11001',t,'provoz',1)<>'AGENT_QUOTA_EXHAUSTED' THEN RAISE EXCEPTION 'Limit jednotlivce'; END IF;
    IF polarita_finops.rezervuj(j,'11001',t,'P1',1)<>'P1_RESERVE_NOT_APPROVED' THEN RAISE EXCEPTION 'P1 bez souhlasu'; END IF;
    IF polarita_finops.rezervuj(j,'17005',t,'eval',1)<>'BUDGET_OK' THEN RAISE EXCEPTION 'Eval jiné pozice'; END IF;
    PERFORM polarita_finops.zauctuj(k,100);
    PERFORM polarita_finops.zauctuj(k,100);
    IF polarita_finops.rezervuj(gen_random_uuid(),'11001',t,'provoz',2875)<>'BUDGET_OK' THEN RAISE EXCEPTION 'Vratka rezervace'; END IF;
END $$;
RESET ROLE;
SET LOCAL ROLE pol_finops_propose;
DO $$ BEGIN
    BEGIN
        PERFORM polarita_finops.navrh(gen_random_uuid(),'17005',gen_random_uuid(),1);
        RAISE EXCEPTION 'Test neodmítl uvolnění sobě' USING ERRCODE='22023';
    EXCEPTION WHEN raise_exception THEN NULL; END;
END $$;
ROLLBACK;
