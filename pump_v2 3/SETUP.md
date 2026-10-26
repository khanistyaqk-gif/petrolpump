# Setup guide: Supabase se Streamlit tak

## A. Supabase project banao
1. https://supabase.com par sign up / login → **New project**.
2. Name: `petrol-pump`. **Database password** set karo aur kahin save kar lo. Region: nearest (India ke liye Mumbai). Create.
3. 1–2 minute wait karo jab tak project ready na ho.

## B. Tables banao
1. Left menu → **SQL Editor** → **New query**.
2. `sql/schema.sql` ka poora content paste karke **Run** dabao. "Success" aana chahiye.
3. **Table Editor** mein 7 tables dikhne chahiye: profiles, shifts, nozzles, fuel_rates, shift_assignments, sale_entries, settlements.
   (Schema RLS ON karta hai bina policy ke. Matlab public anon key kuch padh/likh nahi sakti. Isliye service key zaroori hai, step D.)

## C. Pehla owner user
1. **Authentication → Users → Add user → Create new user**. Email + password daalo, **Auto Confirm User** tick karo.
2. Bane hue user ki row se **UUID** copy karo.
3. SQL Editor mein `sql/first_owner.sql` kholo, `PASTE-USER-UUID-HERE` ki jagah UUID daalo, naam badlo, Run.
4. Manager / salesman ke liye bhi isi tarah Authentication mein user banao. Unke profile app ke Owner → Users page se bante hain.

## D. Keys aur URL copy karo
- **Project URL**: Project Settings → Data API (ya Connect button). Format `https://xxxx.supabase.co`.
- **Keys**: Project Settings → API Keys. Do tarah ki keys hoti hain:
  - Legacy: `anon` aur `service_role` (JWT)
  - Nayi: `publishable` aur `secret` (`sb_publishable_...`, `sb_secret_...`)
  Dono tarah chalti hain (Supabase ke hisaab se legacy keys 2026 ke end tak deprecate hongi).
- Mapping:
  - `SUPABASE_ANON_KEY`    = anon  ya  publishable
  - `SUPABASE_SERVICE_KEY` = service_role  ya  secret  (**secret rakho**, kisi ko mat bhejo, GitHub par mat daalo)
- `APP_SESSION_SECRET` = koi lambi random string. Banane ke liye: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

## E. Apne computer par chalao (optional, pehle test ke liye achha)
```
pip install -r requirements.txt
copy .env.example .env      (Mac/Linux: cp .env.example .env)  → .env mein 4 values bharo
streamlit run app.py
```

## F. GitHub par daalo
1. github.com par **private** repo banao (jaise `petrol-pump-v2`).
2. `pump_v2` folder ke andar ki files repo ke **root** mein upload karo (`app.py` root mein dikhna chahiye).
3. `.env` upload mat karna (`.gitignore` ise rok deta hai).

## G. Streamlit Community Cloud par deploy
1. https://share.streamlit.io → GitHub se login → **Create app** → **Yup, I have an app**.
2. Repository, Branch (`main`), Main file path = `app.py`.
3. **Advanced settings** → Python version `3.12` → **Secrets** mein ye paste karo (quotes zaroori hain):
```
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_ANON_KEY = "..."
SUPABASE_SERVICE_KEY = "..."
APP_SESSION_SECRET = "..."
```
4. Save → Deploy. Build mein kuch minute lagte hain.

## H. Pehli baar check karo
1. Owner se login.
2. **Diagnostics → Health**: Settings aur "Database reachable" hara hona chahiye, mode "service key".
3. **Diagnostics → Schema check**: saari tables OK.
4. Owner → **Fuel Rates**: har fuel ka rate set karo. **Nozzles**: nozzles banao (current meter reading ke saath). **Users**: manager aur salesman ka profile (UUID ke saath).
5. Manager login → **Duty** → duty start → **Nozzle Assignment**. Salesman login → Sale Entry.

## Dikkat aaye to
| Dikha | Matlab |
|---|---|
| Supabase sign-in failed: Invalid login credentials | Email/password galat, ya user Authentication mein nahi hai |
| Email not confirmed | User banate waqt Auto Confirm tick nahi kiya. Authentication → Users mein user par confirm karo |
| Login is correct but no profile exists (UUID dikhega) | `first_owner.sql` chalao ya Owner → Users mein us UUID ka profile banao |
| permission denied for table ... | `SUPABASE_SERVICE_KEY` set nahi hai ya galat hai (RLS anon key ko rokta hai) |
| Invalid API key | Key poori copy nahi hui, ya naye `sb_...` key ke saath purani supabase library. `pip install -U supabase` |
| App not configured. Missing: ... | Secrets mein naam ya quotes galat |
| Sab logout ho jaate hain | `APP_SESSION_SECRET` set nahi hai |
