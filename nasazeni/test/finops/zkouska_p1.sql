BEGIN;
SELECT gen_random_uuid() AS navrh, gen_random_uuid() AS ukol, gen_random_uuid() AS hlas \gset
SET LOCAL ROLE pol_finops_propose;
SELECT polarita_finops.navrh(:'navrh','11001',:'ukol',7050);
RESET ROLE;
INSERT INTO public.approvals SELECT :'hlas',c.id,NULL,'test-spravce','request_board_approval','approved',now(),'test-spravce',
    jsonb_build_object('polaritaFinOps',jsonb_build_object('navrh',:'navrh','rezim','TEST',
          'mesic',to_char(now() AT TIME ZONE 'UTC','YYYY-MM'),'pozice','11001','ukol',:'ukol','centy',7050))
    FROM public.companies c;
-- Nejprve musí celá firma vyčerpat skutečné jednotlivé kvóty.
DO $$ DECLARE q record; BEGIN
    FOR q IN SELECT * FROM polarita_finops.kvoty LOOP
        IF polarita_finops.rezervuj(gen_random_uuid(),q.pozice,gen_random_uuid(),'provoz',q.kvota)<>'BUDGET_OK'
        THEN RAISE EXCEPTION 'Kvóta %',q.pozice; END IF;
    END LOOP;
    IF NOT (polarita_finops.stav()->>'varovani_80')::boolean THEN RAISE EXCEPTION 'Varování 80 %%'; END IF;
END $$;
SET LOCAL ROLE pol_finops_release;
SELECT polarita_finops.uvolni(:'hlas',:'navrh','11001',:'ukol',7050);
RESET ROLE;
SET LOCAL ROLE pol_finops_call;
SELECT polarita_finops.rezervuj(gen_random_uuid(),'11001',gen_random_uuid(),'P1',5,:'hlas')='P1_RESERVE_NOT_APPROVED' AS vazba_ok \gset
\if :vazba_ok
\else
DO $$ BEGIN RAISE EXCEPTION 'Rozsah rozhodnutí nesouhlasí'; END $$;
\endif
SELECT polarita_finops.rezervuj(gen_random_uuid(),'11001',:'ukol','P1',7050,:'hlas')='P1_RESERVE_USED' AS rezerva_ok \gset
\if :rezerva_ok
\else
DO $$ BEGIN RAISE EXCEPTION 'Vazba a čerpání P1'; END $$;
\endif
DO $$ BEGIN
    IF polarita_finops.rezervuj(gen_random_uuid(),'17005',gen_random_uuid(),'eval',1)<>'FINOPS_HARD_STOP'
    THEN RAISE EXCEPTION 'Celofiremní stopka'; END IF;
END $$;
RESET ROLE;
SET LOCAL ROLE pol_finops_read;
DO $$ BEGIN IF NOT (polarita_finops.stav()->>'globalni_stop')::boolean THEN RAISE EXCEPTION 'Souhrnný stav'; END IF; END $$;
ROLLBACK;
