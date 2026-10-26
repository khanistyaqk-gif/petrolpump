# ⛽ Petrol Pump v2 (Streamlit + Supabase)

Poora naya software, naye database ke saath. Saare business rules: `LOGIC.md`.

## Kya kya hai
| Role | Pages |
|---|---|
| Owner | Sab Manager pages + Fuel Rate, Nozzles, Tanks, Users, Settings, System/Backup |
| Manager | Dashboard, Settlement, Duty/Nozzle, Testing, Credit Party, Money Control, Stock, Kharcha, Reports |
| Salesman | Meri Duty (sale entry + hisaab bhejna), Meri Entries |

## Setup (ek baar, ~20 minute)

### 1. Supabase
1. supabase.com → **New project** (region: Mumbai). Database password kahin likh lein.
2. **SQL Editor → New query** → `sql/01_schema.sql` poora paste → **Run**. "Success" aana chahiye.
3. **Authentication → Sign In / Providers → Email**: "Confirm email" band kar dein (salesman ke paas email nahi hota).
4. **Project Settings → API** se copy karein: Project URL, `anon` key, `service_role` key.

### 2. Secrets
`.streamlit/secrets.toml.example` ko `.streamlit/secrets.toml` naam se copy karke bharein.
`APP_SESSION_SECRET` ke liye: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

### 3. Chalayein
```bash
pip install -r requirements.txt
streamlit run app.py
```
Pehli baar khulne par **Owner account banane** ka screen aayega.

### 4. Owner — shuru ka data (ek baar)
1. **Settings:** bank accounts (jaise Canara OD), oil companies (jaise IOCL).
2. **Settings → Opening balance:** galle ka cash, har bank, paytm/ccms (agar baaki), oil company ko dena.
   Party ka purana udhaar bhi yahin.
3. **Tanks:** har fuel ka tank + abhi ka stock.
4. **Nozzles:** har nozzle + meter ki abhi ki reading.
5. **Fuel Rate:** aaj ka rate.
6. **Users:** Manager aur Salesman (login ID jaise `ramesh`).
7. **Credit Party:** parties, limit, gaadi number.

### 5. Deploy (Streamlit Community Cloud)
GitHub par push (`secrets.toml` `.gitignore` mein hai, nahi jayega) → share.streamlit.io → `app.py` →
Settings → Secrets mein secrets.toml ka content paste.

## Roz ka kaam
1. **Duty / Nozzle:** salesman ki duty shuru → nozzle allot (opening apne aap).
2. **Testing** (agar hui).
3. Salesman: **Meri Duty** → entries → Cash/Paytm/CCMS/Credit → "Manager ko bhejein".
4. **Settlement:** closing → hisaab dekhein → save → farak ±₹2 ke andar → **Approve**.
   Approve par ek saath: stock minus, cash/paytm/ccms account mein, party udhaar, duty band.
5. **Money Control:** cash bank mein jama, paytm settlement, CCMS adjust, oil company payment.
6. **Stock:** tanker aaya to inward → approve. Dip → approve.
7. **Kharcha** → approve.
8. **Reports:** din ka hisaab, period sale, salesman, profit/loss, party statement (CSV download).
9. Owner, hafte mein ek baar: **System → Hisaab check** aur **Backup** download.

## Tests
```bash
python -m unittest discover -s tests -v     # 31 hisaab ke tests
```

## Files
```
app.py                 menu (role ke hisaab se)
core/calc.py           SAARA hisaab (Decimal) — tests isi ke
core/auth.py, session.py   login, refresh par login bana rahe
core/db.py, ui.py      Supabase client, formatting
repo/*.py              database ka kaam (har module ek file)
views/*.py             screens
sql/01_schema.sql      poora database: tables, rok, ledgers, approve functions, RLS
```
