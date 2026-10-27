-- =====================================================================
-- Petrol Pump v2 — poora database (naya Supabase project)
-- Supabase > SQL Editor mein poora paste karke ek baar Run karein.
-- Dobara run karna safe hai (tables "if not exists", functions "or replace").
--
-- Paise ka hisaab:  money_txns  — har account ki har aawak/jaawak (+ / -).
--   account: cash | bank | paytm | ccms | oil (oil = oil company ko dena)
--   Balance = sum(amount).  Koi balance "save" nahi hota, hamesha entries se banta hai.
-- Stock ka hisaab:  stock_moves — har tank ki har badhat/ghatat. stock_tanks.current_stock
--   isi ke saath ek hi transaction mein badalta hai.
-- =====================================================================

-- ---------------------------------------------------------------- users
create table if not exists public.profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    name        text not null,
    login       text,
    role        text not null check (role in ('owner', 'manager', 'salesman')),
    phone       text,
    is_active   boolean not null default true,
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------- setup
create table if not exists public.bank_accounts (
    id          bigint generated always as identity primary key,
    name        text not null unique,
    is_active   boolean not null default true,
    created_at  timestamptz not null default now()
);

create table if not exists public.oil_companies (
    id          bigint generated always as identity primary key,
    name        text not null unique,
    is_active   boolean not null default true,
    created_at  timestamptz not null default now()
);

create table if not exists public.nozzles (
    id               bigint generated always as identity primary key,
    nozzle_name      text not null unique,
    fuel_type        text not null check (fuel_type in ('petrol','diesel','premium_petrol','premium_diesel')),
    current_reading  numeric(14,2) not null default 0 check (current_reading >= 0),
    is_active        boolean not null default true,
    created_at       timestamptz not null default now()
);

create table if not exists public.fuel_rates (
    id               bigint generated always as identity primary key,
    fuel_type        text not null check (fuel_type in ('petrol','diesel','premium_petrol','premium_diesel')),
    price_per_liter  numeric(10,2) not null check (price_per_liter > 0),
    effective_from   date not null,
    created_by       uuid references public.profiles(id),
    created_at       timestamptz not null default now(),
    unique (fuel_type, effective_from)
);

create table if not exists public.stock_tanks (
    id               bigint generated always as identity primary key,
    fuel_type        text not null check (fuel_type in ('petrol','diesel','premium_petrol','premium_diesel')),
    tank_name        text not null,
    capacity_liters  numeric(14,2) not null check (capacity_liters > 0),
    opening_stock    numeric(14,2) not null default 0,
    current_stock    numeric(14,2) not null default 0 check (current_stock >= 0),
    is_active        boolean not null default true,
    created_by       uuid references public.profiles(id),
    created_at       timestamptz not null default now()
);
create unique index if not exists uniq_active_tank_per_fuel on public.stock_tanks (fuel_type) where is_active;

-- ---------------------------------------------------------------- duty
create table if not exists public.shifts (
    id           bigint generated always as identity primary key,
    salesman_id  uuid not null references public.profiles(id),
    started_by   uuid references public.profiles(id),
    date         date not null,
    is_active    boolean not null default true,
    started_at   timestamptz not null default now(),
    ended_at     timestamptz,
    created_at   timestamptz not null default now()
);
create unique index if not exists uniq_active_duty_per_salesman on public.shifts (salesman_id) where is_active;

create table if not exists public.shift_assignments (
    id               bigint generated always as identity primary key,
    shift_id         bigint not null references public.shifts(id),
    salesman_id      uuid not null references public.profiles(id),
    nozzle_id        bigint not null references public.nozzles(id),
    opening_reading  numeric(14,2) not null,
    closing_reading  numeric(14,2),
    is_active        boolean not null default true,
    assigned_by      uuid references public.profiles(id),
    created_at       timestamptz not null default now(),
    ended_at         timestamptz,
    check (closing_reading is null or closing_reading >= opening_reading)
);
create unique index if not exists uniq_active_nozzle_assignment on public.shift_assignments (nozzle_id) where is_active;

create table if not exists public.daily_testing (
    id               bigint generated always as identity primary key,
    date             date not null,
    fuel_type        text not null,
    nozzle_id        bigint not null references public.nozzles(id),
    shift_id         bigint references public.shifts(id),
    assignment_id    bigint references public.shift_assignments(id),
    salesman_id      uuid references public.profiles(id),
    reading_before   numeric(14,2) not null,
    reading_after    numeric(14,2) not null,
    testing_liters   numeric(14,2) not null check (testing_liters > 0),
    returned_to_tank boolean not null default true,
    remark           text,
    status           text not null default 'approved' check (status in ('approved','rejected')),
    tested_by        uuid references public.profiles(id),
    created_at       timestamptz not null default now()
);
create index if not exists idx_testing_assignment on public.daily_testing (assignment_id);

create table if not exists public.sale_entries (
    id            bigint generated always as identity primary key,
    shift_id      bigint not null references public.shifts(id),
    nozzle_id     bigint not null references public.nozzles(id),
    salesman_id   uuid not null references public.profiles(id),
    date          date not null,
    entry_time    timestamptz not null default now(),
    fuel_type     text not null,
    liters        numeric(14,2) not null check (liters > 0),
    rate          numeric(10,2) not null check (rate > 0),
    rate_date     date,
    rate_snapshot jsonb,
    amount        numeric(14,2) not null check (amount > 0),
    status        text not null default 'pending' check (status in ('pending','approved','rejected','cancelled')),
    approved_by   uuid references public.profiles(id),
    approved_at   timestamptz,
    created_at    timestamptz not null default now()
);
create index if not exists idx_sale_shift on public.sale_entries (shift_id);
-- Ek duty mein ek nozzle ki ek hi chalu entry (cancel ke baad nayi ho sakti hai)
create unique index if not exists uniq_live_sale_per_nozzle
    on public.sale_entries (shift_id, nozzle_id) where status in ('pending', 'approved');

create table if not exists public.settlements (
    id                            bigint generated always as identity primary key,
    shift_id                      bigint not null unique references public.shifts(id),
    salesman_id                   uuid not null references public.profiles(id),
    date                          date not null,
    nozzle_readings               jsonb not null default '[]'::jsonb,
    meter_total                   numeric(14,2) not null default 0,
    entries_total                 numeric(14,2) not null default 0,
    difference                    numeric(14,2) not null default 0,
    cash_amount                   numeric(14,2) not null default 0 check (cash_amount >= 0),
    paytm_amount                  numeric(14,2) not null default 0 check (paytm_amount >= 0),
    ccms_amount                   numeric(14,2) not null default 0 check (ccms_amount >= 0),
    credit_amount                 numeric(14,2) not null default 0 check (credit_amount >= 0),
    cash_given_to_creditor_amount numeric(14,2) not null default 0 check (cash_given_to_creditor_amount >= 0),
    cash_transfer_expected        numeric(14,2) not null default 0,
    breakup_submitted_at          timestamptz,
    status                        text not null default 'pending' check (status in ('pending','hold','reopened','approved')),
    manager_note                  text,
    approved_by                   uuid references public.profiles(id),
    approved_at                   timestamptz,
    stock_deducted                boolean not null default false,
    stock_deducted_at             timestamptz,
    stock_deducted_by             uuid references public.profiles(id),
    stock_effect                  jsonb,
    created_at                    timestamptz not null default now()
);
create index if not exists idx_settlement_date on public.settlements (date, status);

-- ---------------------------------------------------------------- credit
create table if not exists public.credit_parties (
    id               bigint generated always as identity primary key,
    name             text not null unique,
    phone            text,
    credit_limit     numeric(14,2) not null default 0 check (credit_limit >= 0),
    current_balance  numeric(14,2) not null default 0,
    vehicles         jsonb not null default '[]'::jsonb,
    is_active        boolean not null default true,
    created_by       uuid references public.profiles(id),
    created_at       timestamptz not null default now()
);

create table if not exists public.credit_transactions (
    id               bigint generated always as identity primary key,
    date             date not null,
    party_id         bigint not null references public.credit_parties(id),
    type             text not null check (type in ('opening','sale','cash_given','payment_received')),
    amount           numeric(14,2) not null check (amount > 0),
    payment_mode     text,
    bank_account_id  bigint references public.bank_accounts(id),
    reference_id     text,
    note             text,
    status           text not null default 'pending' check (status in ('pending','hold','reopened','approved','rejected')),
    created_by       uuid references public.profiles(id),
    created_at       timestamptz not null default now(),
    approved_by      uuid references public.profiles(id),
    approved_at      timestamptz,
    approval_note    text
);
create index if not exists idx_credit_ref on public.credit_transactions (reference_id);
create index if not exists idx_credit_party on public.credit_transactions (party_id, date);

-- ---------------------------------------------------------------- money & stock ledgers
create table if not exists public.money_txns (
    id               bigint generated always as identity primary key,
    date             date not null,
    account          text not null check (account in ('cash','bank','paytm','ccms','oil')),
    bank_account_id  bigint references public.bank_accounts(id),
    oil_company_id   bigint references public.oil_companies(id),
    amount           numeric(14,2) not null check (amount <> 0),
    kind             text not null,
    ref_table        text,
    ref_id           text,
    note             text,
    created_by       uuid references public.profiles(id),
    created_at       timestamptz not null default now(),
    check (account <> 'bank' or bank_account_id is not null),
    check (account <> 'oil'  or oil_company_id  is not null)
);
create index if not exists idx_money_date on public.money_txns (date, account);

create table if not exists public.stock_moves (
    id          bigint generated always as identity primary key,
    date        date not null,
    fuel_type   text not null,
    delta       numeric(14,2) not null check (delta <> 0),
    kind        text not null check (kind in ('opening','sale','inward','dip_adjust','correction')),
    ref_table   text,
    ref_id      text,
    note        text,
    created_by  uuid references public.profiles(id),
    created_at  timestamptz not null default now()
);
create index if not exists idx_stock_moves on public.stock_moves (fuel_type, date);

create table if not exists public.fuel_inward (
    id              bigint generated always as identity primary key,
    date            date not null,
    fuel_type       text not null,
    oil_company_id  bigint not null references public.oil_companies(id),
    invoice_no      text,
    liters          numeric(14,2) not null check (liters > 0),
    amount          numeric(14,2) not null check (amount > 0),
    note            text,
    status          text not null default 'pending' check (status in ('pending','approved','rejected')),
    created_by      uuid references public.profiles(id),
    created_at      timestamptz not null default now(),
    approved_by     uuid references public.profiles(id),
    approved_at     timestamptz
);

create table if not exists public.stock_dips (
    id              bigint generated always as identity primary key,
    date            date not null,
    fuel_type       text not null,
    dip_cm          numeric(10,2),
    physical_liters numeric(14,2) not null check (physical_liters >= 0),
    book_liters     numeric(14,2) not null,
    variance        numeric(14,2) not null,
    note            text,
    status          text not null default 'pending' check (status in ('pending','approved','rejected')),
    created_by      uuid references public.profiles(id),
    created_at      timestamptz not null default now(),
    approved_by     uuid references public.profiles(id),
    approved_at     timestamptz
);

create table if not exists public.expenses (
    id               bigint generated always as identity primary key,
    date             date not null,
    category         text not null,
    description      text,
    amount           numeric(14,2) not null check (amount > 0),
    payment_mode     text not null check (payment_mode in ('cash','bank')),
    bank_account_id  bigint references public.bank_accounts(id),
    reference_no     text,
    status           text not null default 'pending' check (status in ('pending','approved','rejected')),
    created_by       uuid references public.profiles(id),
    created_at       timestamptz not null default now(),
    approved_by      uuid references public.profiles(id),
    approved_at      timestamptz,
    check (payment_mode <> 'bank' or bank_account_id is not null)
);

create table if not exists public.audit_log (
    id          bigint generated always as identity primary key,
    action      text not null,
    user_id     text,
    details     jsonb default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

-- =====================================================================
-- Functions (har ek = ek transaction: ya poora kaam, ya kuch nahi)
-- =====================================================================

-- ---------- tank stock badlo + stock_moves (sabka ek hi raasta) ----------
create or replace function public.adjust_tank_v2(
    p_fuel text, p_delta numeric, p_kind text, p_date date,
    p_ref_table text, p_ref_id text, p_note text, p_by uuid
) returns numeric
language plpgsql security definer set search_path = public as $$
declare tk record; v_new numeric;
begin
    if p_delta = 0 then return null; end if;
    select * into tk from stock_tanks where fuel_type = p_fuel and is_active for update;
    if not found then
        raise exception 'No tank is set up for %. Please create one in Owner > Tanks.', p_fuel;
    end if;
    v_new := round(tk.current_stock + p_delta, 2);
    if v_new < 0 then
        raise exception 'Insufficient % stock: tank has % L, required % L', p_fuel, tk.current_stock, -p_delta;
    end if;
    if v_new > tk.capacity_liters then
        raise exception '% tank capacity (% L) would be exceeded (% L)', p_fuel, tk.capacity_liters, v_new;
    end if;
    update stock_tanks set current_stock = v_new where id = tk.id;
    insert into stock_moves (date, fuel_type, delta, kind, ref_table, ref_id, note, created_by)
    values (p_date, p_fuel, round(p_delta, 2), p_kind, p_ref_table, p_ref_id, p_note, p_by);
    return v_new;
end $$;

-- ---------- settlement approve ----------
create or replace function public.approve_settlement_v2(
    p_settlement_id bigint, p_manager_id uuid, p_tolerance numeric default 2
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
    s record; fl record; tx record;
    v_pay numeric; v_diff numeric; v_cash_in numeric;
    v_effect jsonb := '{}'::jsonb; v_new numeric; v_missing text;
begin
    select * into s from settlements where id = p_settlement_id for update;
    if not found then raise exception 'Settlement not found'; end if;
    if s.status = 'approved' or s.stock_deducted then
        raise exception 'This settlement has already been approved';
    end if;
    if jsonb_array_length(s.nozzle_readings) = 0 then
        raise exception 'Please save the closing readings first';
    end if;
    -- Duty ke har nozzle ki closing honi chahiye (closing ke baad allot hua nozzle chhoot na jaye)
    select string_agg(n.nozzle_name, ', ') into v_missing
      from shift_assignments a join nozzles n on n.id = a.nozzle_id
     where a.shift_id = s.shift_id and a.is_active;
    if v_missing is not null then
        raise exception 'Closing reading pending for: %. Please save the closing first.', v_missing;
    end if;
    select string_agg(n.nozzle_name, ', ') into v_missing
      from shift_assignments a join nozzles n on n.id = a.nozzle_id
     where a.shift_id = s.shift_id and a.closing_reading is not null
       and not exists (select 1 from jsonb_array_elements(s.nozzle_readings) x
                        where (x->>'assignment_id')::bigint = a.id);
    if v_missing is not null then
        raise exception 'Please save the closing again (% is not included).', v_missing;
    end if;
    if s.meter_total > 0 and s.breakup_submitted_at is null then
        raise exception 'The salesman has not submitted the payment settlement yet';
    end if;

    v_pay  := s.cash_amount + s.paytm_amount + s.ccms_amount + s.credit_amount;
    v_diff := round(s.meter_total - v_pay, 2);
    if abs(v_diff) > p_tolerance then
        raise exception 'Difference is Rs % (more than ±%). Please hold or return the settlement.', v_diff, p_tolerance;
    end if;
    if s.cash_given_to_creditor_amount > s.cash_amount then
        raise exception 'Cash advanced to credit parties exceeds total cash';
    end if;

    -- 1. Stock: har fuel ka net sale litre minus
    for fl in
        select x->>'fuel_type' as fuel_type,
               round(sum((x->>'net_sale_liters')::numeric), 2) as liters
          from jsonb_array_elements(s.nozzle_readings) x
         group by 1
    loop
        if fl.liters > 0 then
            v_new := adjust_tank_v2(fl.fuel_type, -fl.liters, 'sale', s.date,
                                    'settlements', s.id::text, null, p_manager_id);
            v_effect := v_effect || jsonb_build_object(fl.fuel_type,
                        jsonb_build_object('sale_liters', fl.liters, 'new_stock', v_new));
        end if;
    end loop;

    -- 2. Paisa: cash (creditor ko diya ghata ke), paytm, ccms
    v_cash_in := s.cash_amount - s.cash_given_to_creditor_amount;
    if v_cash_in > 0 then
        insert into money_txns (date, account, amount, kind, ref_table, ref_id, created_by)
        values (s.date, 'cash', v_cash_in, 'sale', 'settlements', s.id::text, p_manager_id);
    end if;
    if s.paytm_amount > 0 then
        insert into money_txns (date, account, amount, kind, ref_table, ref_id, created_by)
        values (s.date, 'paytm', s.paytm_amount, 'sale', 'settlements', s.id::text, p_manager_id);
    end if;
    if s.ccms_amount > 0 then
        insert into money_txns (date, account, amount, kind, ref_table, ref_id, created_by)
        values (s.date, 'ccms', s.ccms_amount, 'sale', 'settlements', s.id::text, p_manager_id);
    end if;

    -- 3. Credit: party balance + approve
    for tx in
        select * from credit_transactions
         where reference_id = s.id::text and type in ('sale','cash_given')
           and status in ('pending','hold','reopened')
         for update
    loop
        update credit_parties set current_balance = current_balance + tx.amount where id = tx.party_id;
        update credit_transactions
           set status = 'approved', approved_by = p_manager_id, approved_at = now(),
               approval_note = 'Approved with settlement'
         where id = tx.id;
    end loop;

    -- 4. Entries, settlement, duty
    update sale_entries set status = 'approved', approved_by = p_manager_id, approved_at = now()
     where shift_id = s.shift_id and salesman_id = s.salesman_id and status = 'pending';

    update settlements
       set status = 'approved', approved_by = p_manager_id, approved_at = now(), difference = v_diff,
           cash_transfer_expected = v_cash_in,
           stock_deducted = true, stock_deducted_at = now(), stock_deducted_by = p_manager_id,
           stock_effect = v_effect
     where id = s.id;

    update shift_assignments set is_active = false, ended_at = coalesce(ended_at, now())
     where shift_id = s.shift_id and is_active;
    update shifts set is_active = false, ended_at = coalesce(ended_at, now()) where id = s.shift_id;

    return jsonb_build_object('ok', true, 'difference', v_diff, 'stock_effect', v_effect);
end $$;

-- ---------- party se payment ----------
create or replace function public.record_party_payment_v2(
    p_party_id bigint, p_amount numeric, p_mode text, p_bank_id bigint,
    p_date date, p_ref text, p_note text, p_by uuid
) returns bigint
language plpgsql security definer set search_path = public as $$
declare v_id bigint; p record;
begin
    if p_amount is null or p_amount <= 0 then raise exception 'Amount must be greater than 0'; end if;
    if p_mode not in ('cash','bank','paytm','ccms') then raise exception 'Invalid payment mode'; end if;
    if p_mode = 'bank' and p_bank_id is null then raise exception 'Please select a bank account'; end if;
    select * into p from credit_parties where id = p_party_id for update;
    if not found then raise exception 'Party not found'; end if;

    insert into credit_transactions (date, party_id, type, amount, payment_mode, bank_account_id,
                                     reference_id, note, status, created_by, approved_by, approved_at)
    values (p_date, p_party_id, 'payment_received', round(p_amount, 2), p_mode,
            case when p_mode = 'bank' then p_bank_id end, p_ref, p_note, 'approved', p_by, p_by, now())
    returning id into v_id;

    update credit_parties set current_balance = current_balance - round(p_amount, 2) where id = p_party_id;

    insert into money_txns (date, account, bank_account_id, amount, kind, ref_table, ref_id, note, created_by)
    values (p_date, p_mode, case when p_mode = 'bank' then p_bank_id end, round(p_amount, 2),
            'party_payment', 'credit_transactions', v_id::text, p.name, p_by);
    return v_id;
end $$;

-- ---------- party opening balance ----------
create or replace function public.party_opening_v2(
    p_party_id bigint, p_amount numeric, p_date date, p_by uuid
) returns void
language plpgsql security definer set search_path = public as $$
begin
    if p_amount is null or p_amount <= 0 then raise exception 'Amount must be greater than 0'; end if;
    if exists (select 1 from credit_transactions where party_id = p_party_id and type = 'opening') then
        raise exception 'Opening balance for this party has already been entered';
    end if;
    perform 1 from credit_parties where id = p_party_id for update;
    insert into credit_transactions (date, party_id, type, amount, status, note, created_by, approved_by, approved_at)
    values (p_date, p_party_id, 'opening', round(p_amount, 2), 'approved', 'Opening balance', p_by, p_by, now());
    update credit_parties set current_balance = current_balance + round(p_amount, 2) where id = p_party_id;
end $$;

-- ---------- tanker inward approve ----------
create or replace function public.approve_inward_v2(p_id bigint, p_by uuid) returns void
language plpgsql security definer set search_path = public as $$
declare r record;
begin
    select * into r from fuel_inward where id = p_id for update;
    if not found then raise exception 'Fuel purchase entry not found'; end if;
    if r.status <> 'pending' then raise exception 'This entry is already %', r.status; end if;
    perform adjust_tank_v2(r.fuel_type, r.liters, 'inward', r.date, 'fuel_inward', r.id::text,
                           coalesce(r.invoice_no, ''), p_by);
    insert into money_txns (date, account, oil_company_id, amount, kind, ref_table, ref_id, note, created_by)
    values (r.date, 'oil', r.oil_company_id, r.amount, 'fuel_inward', 'fuel_inward', r.id::text,
            'Invoice ' || coalesce(r.invoice_no, '-'), p_by);
    update fuel_inward set status = 'approved', approved_by = p_by, approved_at = now() where id = r.id;
end $$;

-- ---------- dip approve (stock = physical, beech ke badlav ke saath) ----------
create or replace function public.approve_dip_v2(p_id bigint, p_by uuid) returns numeric
language plpgsql security definer set search_path = public as $$
declare r record; v_new numeric;
begin
    select * into r from stock_dips where id = p_id for update;
    if not found then raise exception 'Dip entry not found'; end if;
    if r.status <> 'pending' then raise exception 'This entry is already %', r.status; end if;
    if r.variance <> 0 then
        v_new := adjust_tank_v2(r.fuel_type, r.variance, 'dip_adjust', r.date, 'stock_dips', r.id::text,
                                r.note, p_by);
    end if;
    update stock_dips set status = 'approved', approved_by = p_by, approved_at = now() where id = r.id;
    return v_new;
end $$;

-- ---------- kharcha approve ----------
create or replace function public.approve_expense_v2(p_id bigint, p_by uuid) returns void
language plpgsql security definer set search_path = public as $$
declare r record; v_cash numeric;
begin
    select * into r from expenses where id = p_id for update;
    if not found then raise exception 'Expense not found'; end if;
    if r.status <> 'pending' then raise exception 'This expense is already %', r.status; end if;
    if r.payment_mode = 'cash' then
        perform pg_advisory_xact_lock(hashtext('money_cash'));
        select coalesce(sum(amount), 0) into v_cash from money_txns where account = 'cash';
        if v_cash < r.amount then
            raise exception 'Insufficient cash in hand: Rs % available, expense Rs %', v_cash, r.amount;
        end if;
    end if;
    insert into money_txns (date, account, bank_account_id, amount, kind, ref_table, ref_id, note, created_by)
    values (r.date, r.payment_mode, case when r.payment_mode = 'bank' then r.bank_account_id end,
            -r.amount, 'expense', 'expenses', r.id::text, r.category, p_by);
    update expenses set status = 'approved', approved_by = p_by, approved_at = now() where id = r.id;
end $$;

-- ---------- paisa ek account se dusre mein (deposit, paytm settle, ccms adjust, oil payment) ----------
create or replace function public.money_transfer_v2(
    p_kind text, p_date date, p_amount numeric,
    p_from text, p_from_bank bigint, p_to text, p_to_bank bigint, p_oil_company bigint,
    p_ref text, p_note text, p_by uuid
) returns void
language plpgsql security definer set search_path = public as $$
declare v_bal numeric; v_from_amt numeric; v_to_amt numeric;
begin
    if p_amount is null or p_amount <= 0 then raise exception 'Amount must be greater than 0'; end if;
    -- cash / paytm / ccms minus mein nahi ja sakte (bank OD/CC ja sakta hai)
    if p_from in ('cash','paytm','ccms') then
        perform pg_advisory_xact_lock(hashtext('money_' || p_from));
        select coalesce(sum(amount), 0) into v_bal from money_txns where account = p_from;
        if v_bal < p_amount then
            raise exception 'Only Rs % available in %, cannot withdraw Rs %', v_bal, p_from, p_amount;
        end if;
    end if;
    v_from_amt := -round(p_amount, 2);
    -- oil company ko dena: payment / ccms adjust se ghatta hai
    v_to_amt := case when p_to = 'oil' then -round(p_amount, 2) else round(p_amount, 2) end;

    insert into money_txns (date, account, bank_account_id, oil_company_id, amount, kind, ref_id, note, created_by)
    values (p_date, p_from, case when p_from = 'bank' then p_from_bank end, null, v_from_amt, p_kind, p_ref, p_note, p_by);
    insert into money_txns (date, account, bank_account_id, oil_company_id, amount, kind, ref_id, note, created_by)
    values (p_date, p_to, case when p_to = 'bank' then p_to_bank end,
            case when p_to = 'oil' then p_oil_company end, v_to_amt, p_kind, p_ref, p_note, p_by);
end $$;

-- ---------- Sirf server (service_role) chala sake ----------
do $$
declare f text;
begin
    foreach f in array array[
        'adjust_tank_v2(text,numeric,text,date,text,text,text,uuid)',
        'approve_settlement_v2(bigint,uuid,numeric)',
        'record_party_payment_v2(bigint,numeric,text,bigint,date,text,text,uuid)',
        'party_opening_v2(bigint,numeric,date,uuid)',
        'approve_inward_v2(bigint,uuid)',
        'approve_dip_v2(bigint,uuid)',
        'approve_expense_v2(bigint,uuid)',
        'money_transfer_v2(text,date,numeric,text,bigint,text,bigint,bigint,text,text,uuid)'
    ] loop
        execute format('revoke all on function public.%s from public, anon, authenticated', f);
        execute format('grant execute on function public.%s to service_role', f);
    end loop;
end $$;

-- ---------- RLS: browser wali anon key se koi table na khule ----------
do $$
declare t text;
begin
    foreach t in array array['profiles','bank_accounts','oil_companies','nozzles','fuel_rates','stock_tanks',
        'shifts','shift_assignments','daily_testing','sale_entries','settlements','credit_parties',
        'credit_transactions','money_txns','stock_moves','fuel_inward','stock_dips','expenses','audit_log']
    loop
        execute format('alter table public.%I enable row level security', t);
    end loop;
end $$;

-- ---------- Server (service_role) ko tables ki permission ----------
-- Naye Supabase projects mein SQL se bani tables apne aap Data API ko nahi milti.
grant usage on schema public to service_role;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant all on sequences to service_role;
