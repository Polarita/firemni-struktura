CREATE TABLE public.companies (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text, budget_monthly_cents integer);
CREATE TABLE public.agents (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), company_id uuid REFERENCES companies,
                            metadata jsonb, budget_monthly_cents integer);
CREATE TABLE public."user" (id text PRIMARY KEY, email text);
CREATE TABLE public.instance_user_roles (user_id text, role text);
CREATE TABLE public.approvals (id uuid PRIMARY KEY, company_id uuid, requested_by_agent_id uuid, requested_by_user_id text,
                               type text, status text, decided_at timestamptz, decided_by_user_id text, payload jsonb);
CREATE TABLE public.cost_events (company_id uuid, agent_id uuid, occurred_at timestamptz, cost_cents numeric);
INSERT INTO public.companies(name,budget_monthly_cents) VALUES('Polarita s.r.o.',47000);
INSERT INTO public.agents(company_id,metadata,budget_monthly_cents)
    SELECT c.id,jsonb_build_object('polaritaId',q.pozice),q.kvota
    FROM public.companies c,jsonb_to_recordset(:'kvoty'::jsonb) q(pozice text,kvota integer);
INSERT INTO public."user" VALUES('test-spravce','spravce@polarita.test');
INSERT INTO public.instance_user_roles VALUES('test-spravce','instance_admin');
