-- Ek duty mein ek nozzle ki ek hi chalu entry (cancel ke baad nayi ho sakti hai)
create unique index if not exists uniq_live_sale_per_nozzle
    on public.sale_entries (shift_id, nozzle_id) where status in ('pending', 'approved');
