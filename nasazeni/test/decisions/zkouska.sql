-- Všechny zkušební změny včetně potvrzení se na konci vrátí.
BEGIN;
DO $$
BEGIN
    IF polarita.test_okno('2026-03-28 19:00+01','DENNI') <> timestamptz '2026-03-29 07:30+02'
        OR polarita.test_okno('2026-10-24 19:00+02','DENNI') <> timestamptz '2026-10-25 07:30+01'
        OR polarita.test_okno('2026-06-10 07:30+02','DENNI') <> timestamptz '2026-06-10 07:30+02'
        OR polarita.test_okno('2026-06-10 07:31+02','DENNI') <> timestamptz '2026-06-10 16:30+02'
        OR polarita.test_okno('2026-06-10 21:00+02','URGENT') <> timestamptz '2026-06-10 21:00+02' THEN
        RAISE EXCEPTION 'Chyba přidělení dávky';
    END IF;
END $$;
INSERT INTO polarita.test_spis VALUES ('TEST-POL-0000-00000', 1, 'rozpracován');
SET LOCAL ROLE pol_decisions_proposer;
DO $$
DECLARE a uuid := '00000000-0000-4000-8000-000000000001';
BEGIN
    PERFORM polarita.test_navrh(a,'TEST-POL-0000-00000',1,'ke kontrole','URGENT');
    PERFORM polarita.test_navrh(a,'TEST-POL-0000-00000',1,'ke kontrole','URGENT');
    BEGIN
        PERFORM polarita.test_navrh(a,'TEST-POL-0000-00000',1,'uzavřen','URGENT');
        RAISE EXCEPTION 'Chybně povolena výměna diffu' USING ERRCODE='XX000';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM <> 'Identifikátor patří jinému návrhu' THEN RAISE; END IF;
    END;
    PERFORM polarita.test_navrh('00000000-0000-4000-8000-000000000002','TEST-POL-0000-00000',1,'uzavřen','URGENT');
    PERFORM polarita.test_navrh('00000000-0000-4000-8000-000000000003','TEST-POL-0000-00000',1,'uzavřen','DENNI');
    BEGIN
        PERFORM polarita.test_rozhodni(a,'mutation_confirm');
        RAISE EXCEPTION 'Navrhovatel mohl potvrdit svůj návrh';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    IF (SELECT stav FROM polarita.test_spis WHERE cislo='TEST-POL-0000-00000') <> 'rozpracován'
        OR NOT EXISTS (SELECT FROM polarita.test_rozhodnuti WHERE id=a AND pred='rozpracován'
                       AND po='ke kontrole' AND verze_pred=1 AND akce IS NULL) THEN
        RAISE EXCEPTION 'Chybný diff nebo předčasná změna';
    END IF;
END $$;
RESET ROLE;
-- Deterministická zkouška před otevřením okna i v okamžiku skutečného spuštění v 07:30.
UPDATE polarita.test_rozhodnuti SET dostupne = now() + interval '1 hour' WHERE id='00000000-0000-4000-8000-000000000003';
SET LOCAL ROLE pol_decisions_reviewer;
DO $$
DECLARE a uuid := '00000000-0000-4000-8000-000000000001';
        b uuid := '00000000-0000-4000-8000-000000000002';
        c uuid := '00000000-0000-4000-8000-000000000003';
BEGIN
    BEGIN
        UPDATE polarita.test_spis SET stav='uzavřen' WHERE cislo='TEST-POL-0000-00000';
        RAISE EXCEPTION 'Hodnotitel mohl obejít frontu';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM polarita.test_rozhodni(c,'mutation_confirm');
        RAISE EXCEPTION 'Chybně přijatá předčasná dávka' USING ERRCODE='XX000';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM <> 'Denní dávka ještě není otevřená' THEN RAISE; END IF;
    END;
    PERFORM polarita.test_rozhodni(a,'mutation_confirm');
    PERFORM polarita.test_rozhodni(a,'mutation_confirm');
    BEGIN
        PERFORM polarita.test_rozhodni(b,'mutation_confirm');
        RAISE EXCEPTION 'Chybně přijatá stará verze';
    EXCEPTION WHEN serialization_failure THEN NULL;
    END;
    PERFORM polarita.test_rozhodni(b,'mutation_cancel');
    PERFORM polarita.test_rozhodni(b,'mutation_cancel');
    BEGIN
        PERFORM polarita.test_rozhodni(b,'mutation_confirm');
        RAISE EXCEPTION 'Potvrzení zamítnuté položky uspělo' USING ERRCODE='XX000';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM <> 'Položka je již vyřízená' THEN RAISE; END IF;
    END;
    IF NOT EXISTS (SELECT FROM polarita.test_spis WHERE cislo='TEST-POL-0000-00000' AND stav='ke kontrole' AND verze=2)
        OR NOT EXISTS (SELECT FROM polarita.test_rozhodnuti WHERE id=a AND akce='mutation_confirm' AND rozhodnuto IS NOT NULL)
        OR NOT EXISTS (SELECT FROM polarita.test_rozhodnuti WHERE id=b AND akce='mutation_cancel' AND rozhodnuto IS NOT NULL)
        OR NOT EXISTS (SELECT FROM polarita.test_rozhodnuti WHERE id=c AND akce IS NULL) THEN
        RAISE EXCEPTION 'Chybný konečný stav';
    END IF;
END $$;
ROLLBACK;
