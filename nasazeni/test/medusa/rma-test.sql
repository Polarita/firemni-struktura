BEGIN;
SET LOCAL ROLE db_eshop;
DO $test$
DECLARE
    id1 uuid := gen_random_uuid(); id2 uuid := gen_random_uuid(); zmena uuid := gen_random_uuid();
    asserted timestamptz := now()-interval '4 days'; doruceno timestamptz := now()-interval '1 day';
    v wms.rma_prehled;
BEGIN
    PERFORM wms.prijmi_rma(id1,'obj-test',doruceno,asserted,'b2b_servis');
    SELECT * INTO v FROM wms.zarad_rma(id1,zmena,1,'b2c_reklamace',NULL);
    IF v.druh <> 'b2c_reklamace' OR v.complaint_asserted_at IS DISTINCT FROM asserted OR v.received_at <> doruceno
    THEN RAISE EXCEPTION 'Časy reklamace se změnily'; END IF;
    SELECT * INTO v FROM wms.prijmi_rma(id1,'obj-test',doruceno,asserted,'b2b_servis');
    IF v.verze<>2 OR v.druh<>'b2c_reklamace' THEN RAISE EXCEPTION 'Opakovaný příjem změnil stav'; END IF;
    PERFORM wms.zarad_rma(id1,zmena,1,'b2c_reklamace',NULL);
    BEGIN
        PERFORM wms.zarad_rma(id1,zmena,1,'k_posouzeni',NULL);
        RAISE EXCEPTION 'Povolena kolize požadavků';
    EXCEPTION WHEN unique_violation THEN NULL; END;
    BEGIN
        PERFORM wms.zarad_rma(id1,gen_random_uuid(),1,'b2b_servis',NULL);
        RAISE EXCEPTION 'Přepsána novější změna';
    EXCEPTION WHEN serialization_failure THEN NULL; END;
    BEGIN
        PERFORM wms.zarad_rma(id1,gen_random_uuid(),2,'b2c_reklamace',doruceno);
        RAISE EXCEPTION 'Povolen posun času uplatnění';
    EXCEPTION WHEN invalid_parameter_value THEN NULL; END;
    BEGIN
        UPDATE wms.rma SET puvodni_uplatneni=doruceno WHERE id=id1;
        RAISE EXCEPTION 'Povolen přímý přepis';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    PERFORM wms.prijmi_rma(id2,NULL,doruceno,NULL,'k_posouzeni');
    BEGIN
        PERFORM wms.zarad_rma(id2,gen_random_uuid(),1,'b2c_reklamace',NULL);
        RAISE EXCEPTION 'Chybí doklad původního okamžiku';
    EXCEPTION WHEN invalid_parameter_value THEN NULL; END;
    PERFORM wms.zarad_rma(id2,gen_random_uuid(),1,'b2c_reklamace',asserted);
    SELECT * INTO v FROM wms.zarad_rma(id2,gen_random_uuid(),2,'k_posouzeni',NULL);
    IF v.complaint_asserted_at IS DISTINCT FROM asserted OR v.received_at<>doruceno THEN
        RAISE EXCEPTION 'Reklasifikace ztratila později doložený čas';
    END IF;
END $test$;
ROLLBACK;
