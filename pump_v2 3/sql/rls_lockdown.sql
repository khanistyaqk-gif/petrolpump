-- Run in Supabase SQL editor ONLY AFTER:
--   1. SUPABASE_SERVICE_KEY is set in your deployment (Streamlit secrets / .env)
--   2. The app has been redeployed and you confirmed login + data pages work.
--
-- Effect: Row Level Security is enabled with NO policies on every app table.
-- The public anon key (visible in any browser) can then read/write nothing.
-- The service-role key used by the app server bypasses RLS, so the app
-- keeps working. Auth login (supabase.auth) is not affected.
--
-- Rollback for a table:  ALTER TABLE public.<name> DISABLE ROW LEVEL SECURITY;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'profiles','shifts','shift_assignments','nozzles','fuel_rates',
    'sale_entries','settlements','credit_parties','credit_transactions',
    'oil_company_ledger','stock_tanks','stock_closing','daily_testing',
    'fuel_inward','inward_payments','expenses','whatsapp_messages',
    'paytm_settlements','ccms_settlements','cash_deposits'
  ]
  LOOP
    IF to_regclass('public.' || t) IS NOT NULL THEN
      EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    END IF;
  END LOOP;
END $$;
