# Petrol Pump v2 — Business Logic

Har rule yahan likha jayega. Code isi file ke hisaab se banega.

Status:
- ✅ Final
- 📦 Purane app (petrol_pump-main) se liya logic — ab v2 ka rule
- ⚠️ Purane app mein galti / kami mili — aapka faisla chahiye
- 📝 Draft (confirm baaki)

---

## 1. Roles
- ✅ Teen role: Owner, Manager, Salesman. Har ek ka alag login aur menu.
- ✅ User sirf Owner bana sakta hai.
- 📦 Owner sab kuch kar sakta hai + Users, Nozzles, Fuel Rates, System Audit, Backup/Restore.
- 📦 Manager: Dashboard, Money Control, Reports, Sale Approval, Settlement, Credit, Stock, Duty, Nozzle Assignment.
- 📦 Salesman: apni Sale Entry, My Entries, My Summary. **Login sirf tab, jab uski duty chalu ho.**

---

## 2. Duty aur Nozzle

- 📦 Duty **Manager shuru karta hai**, salesman ke liye.
- 📦 Ek salesman ki ek waqt mein ek hi duty chalu ho sakti hai.
- 📦 Ek duty mein **kai nozzle** diye ja sakte hain (jaise petrol + diesel).
- ✅ Ek nozzle ek waqt mein sirf ek salesman ko. Duty band hone tak kisi dusre ko nahi milega.
  (Database level par bhi rok.)
- 📦 Band (inactive) nozzle allot nahi ho sakta. Chalu allotment ke beech nozzle band kiya to allotment apne aap khatam.
- ✅📦 **Opening reading apne aap** = nozzle ki pichli closing reading. Haath se nahi daali jayegi.
- 📦 Duty band hone par uske saare nozzle free ho jaate hain.

---

## 3. Fuel Rate

- 📦 Fuel type: petrol, diesel, premium petrol, premium diesel.
- 📦 Rate sirf Owner set karta hai. Rate 0 se zyada hona chahiye.
- 📦 Har fuel ka **ek din ka ek rate** (rate + "kis tarikh se laagu"). Usi din dobara daala to purana badal jaata hai.
- 📦 Kisi tarikh ka rate = us tarikh ya usse pehle ka sabse naya rate.
- 📦 Agar us tarikh ke baad sale ho chuki hai aur rate badla ja raha hai to warning dikhegi.
- ✅ Rate history kabhi delete/overwrite nahi (alag tarikhon ki).
- ✅📦 **Rate lock:** sale ke waqt jo rate laga, wahi save hota hai. Report hamesha saved amount jodti hai.
  Baad mein rate badalne se purani sale ka amount nahi badalta.
- 📦 Poori duty **duty ki tarikh ke rate** se chalti hai. Closing agle din save ho tab bhi duty wale din ka rate.
- ⚠️ **R1 — Duty ke beech rate badla:** purana app poori duty ek hi rate (duty ki tarikh) se ginta hai.
  Raat 10 baje se subah 8 baje ki duty mein 6 baje rate badla to 6–8 baje ki sale purane rate se jayegi.
  Faisla: (a) rate badalte waqt reading lekar do hisse, ya (b) purane app jaisa hi?

---

## 4. Salesman — Sale Entry (shift ke dauran)

- 📦 Salesman sirf apne allot nozzle par entry kar sakta hai.
- 📦 Har entry: nozzle + litre (0 se zyada). Rate apne aap lock, amount = litre × rate (2 decimal).
- 📦 Entry ka status: pending → approved (settlement approve hone par). Rejected/cancelled entry kisi total mein nahi judti.

- ✅ **Ek nozzle, ek entry:** ek duty mein har nozzle ki ek hi entry. Entry ke baad nozzle 🔒 lock.
  Badlav: **✏️ Edit** (litre badlo — rate wahi jo entry ke waqt laga) ya **❌ Cancel** (nozzle phir khul jata hai).
  Hisaab bhejne ke baad Edit/Cancel band — Manager reopen kare tabhi. Database bhi duplicate rokta hai.
  Har Edit/Cancel audit log mein.

## 5. Salesman — Payment Breakup (duty end)

- 📦 Salesman batata hai: **Cash + Paytm (UPI) + CCMS (card) + Credit**.
- 📦 Ye chaaron mil kar **uski sale entries ke total ke barabar** hone chahiye, warna submit nahi hoga.
- 📦 Credit: har party ke liye amount, gaadi number, comment.
- 📦 **Creditor ko cash diya:** salesman ne galle se kisi party ko cash diya (udhaar).
  - Ye sale matching mein nahi judta.
  - Party ke khate mein lena (balance +) banta hai.
  - Manager ko jama hone wala cash = Cash − creditor ko diya cash.
- 📦 Submit ke baad salesman dobara submit nahi kar sakta. Manager reject/reopen kare tabhi.

---

## 6. Testing

- ✅📦 Testing ke litre **sale mein count nahi** honge. Salesman se testing ka paisa nahi.
- 📦 Testing entry Manager/Owner karta hai: nozzle + litre + remark.
- 📦 Testing karte hi nozzle ki meter reading utne litre aage badh jaati hai.
- ✅📦 Testing ka fuel **tank mein wapas** → stock par asar 0.
  Wapas nahi gaya (loss) → approve hone par stock se ghatega.
- 📦 Nozzle kisi chalu duty mein hai to testing usi duty se jud jaati hai.
- 📦 Testing litre gross litre se zyada ho to closing save nahi hogi.
- ✅ **R2 (v2 mein theek):** testing ab allotment se match hoti hai, tarikh se nahi.
- ~~R2 — Raat ki duty mein testing:~~ testing duty ki *tarikh* se match hoti hai.
  Duty 25 ko shuru hui aur testing 26 ko (raat 12 ke baad) hui to wo minus nahi hogi → salesman par galat short.
  Sujhaav: testing ko tarikh se nahi, duty (assignment) se match karein.

---

## 7. Manager — Closing Reading aur Settlement

- 📦 Har allot nozzle ki closing reading zaroori. Closing ≥ opening.
- 📦 Hisaab (har nozzle):
  - Gross litre = closing − opening
  - Net sale litre = gross − testing
  - Amount = net litre × locked rate
- 📦 Har nozzle ka poora snapshot save: opening, closing, gross, testing, net, rate, amount.
- 📦 Closing save hote hi nozzle ki current reading = closing (agli duty ki opening).
- 📦 **Difference = Meter amount − (Cash + Paytm + CCMS + Credit)**
- 📦 **±₹2 tak ka farak "matched"** maana jaata hai.
- 📦 Approve tabhi jab: closing save ho + farak ±₹2 ke andar. Warna Hold ya Reopen.
- 📦 Approve hone par ek saath:
  1. Tank stock se net litre minus (fuel-wise). Tank na ho ya stock kam pade to approve ruk jaata hai. Ek baar hi minus.
  2. Salesman ki saari sale entries approved.
  3. Credit entries approved → party ka balance update → party ko WhatsApp message.
- 📦 Approved settlement badla nahi ja sakta.
- 📦 Status: pending → approved / hold / reopened.

---

- ✅ **Approve tabhi jab duty ke har nozzle ki closing ho** aur saved closing mein har nozzle ho
  (closing ke baad naya nozzle allot hua to pehle uski closing).
- ✅ Salesman hisaab bhejte waqt jis nozzle ki entry nahi hai uski warning dekhta hai.

---

## 8. Credit Party (Udhaar)

- ✅ Party: naam, phone, credit limit, gaadiyon ki list, active/band.
- ✅ Khate ki entries:
  - Lena badhta (+): opening (purana udhaar, ek baar), fuel udhaar, creditor ko cash diya
  - Lena ghatta (−): party se payment mila (cash / bank / paytm / ccms)
- ✅ Udhaar aur "cash diya" sirf **settlement approve** par balance mein judte hain.
- ✅ Party se payment Manager darj karta hai → turant balance kam + paisa us account mein (ek transaction).
- ✅ **R3:** limit paar hone par **warning** (rok nahi).
- ✅ **R4:** party ki gaadi list ho to sirf list wali gaadi par udhaar. List khali = koi bhi gaadi.
- ⏳ Galat party mein gaya udhaar sudhaarna (transfer) — abhi nahi, zaroorat ho to bataiye.

---

## 9. Stock

- ✅ Har fuel ka ek tank: naam, capacity, stock. Petrol, diesel, premium petrol, premium diesel.
- ✅ Tank ka stock **sirf ek raaste** se badalta hai (`adjust_tank_v2`) aur har badlav `stock_moves` register mein.
  Stock 0 se kam ya capacity se zyada nahi ho sakta.
- ✅ **R5:** jis fuel ki sale hui uska tank zaroori — tank na ho to approve ruk jayega.
- ✅ **R6 — Stock register:** har din: opening (= kal ki closing) + inward − sale ± dip farak ± sudhaar = closing.
- ✅ **R7 — Tanker inward ek hi raasta:** Manager entry (pending) → Approve par tank + aur oil company ko dena +bill.
  Same company ka same bill number dobara nahi. Capacity se zyada ho to approve ruk jayega.
- ✅ **Dip:** asli stock darj → book stock usi waqt save → Approve par farak (asli − book) tank mein adjust.
  Ek fuel ki ek hi dip pending. (Entry aur approve ke beech sale approve ho jaye tab bhi hisaab sahi rehta hai.)
- ✅ Testing ka fuel tank mein wapas → stock par asar 0.
- ✅ Haath se stock sudhaar sirf Owner, kaaran ke saath.

---

## 10. Paisa (Money Control)

- ✅ Khate: **Cash (galla), Bank (Owner jitne chahe jode), Paytm/UPI, CCMS/Card, Oil company ko dena.**
- ✅ Har aawak/jaawak `money_txns` mein. Balance hamesha entries ka jod — kahin alag se save nahi.
- ✅ Settlement approve par: cash +(cash − creditor ko diya), paytm +, ccms +.
- ✅ **R8:** creditor ko diya cash galle mein nahi gina jaata.
- ✅ Cash bank mein jama: cash −, bank +.
- ✅ Paytm settlement: paytm −, bank +.
- ✅ **CCMS bank mein nahi aata** — CCMS −, oil company ko dena −.
- ✅ Oil company payment: bank −, dena −.
- ✅ Tanker bill approve: dena +.
- ✅ **Cash, Paytm, CCMS kabhi minus nahi** — jitna hai usse zyada nahi nikal sakte. Bank minus ho sakta hai (OD/CC).
- ✅ Opening balance: har account ka ek hi baar (Owner > Settings).

## 11. Kharcha (Expense)

- ✅ Category: salary, bijli, maintenance, transport, office, bank charges, kiraya, misc.
- ✅ Cash ya bank se. Entry pending → Approve par paisa minus. Cash se tabhi jab galle mein utna cash ho.

## 12. Profit / Loss

- ✅ **R9:** Net profit = sale − **laagat** − kharcha.
  Laagat = bika litre × us fuel ka **aakhri tanker rate** (bill ÷ litre). Poora tanker bill ek din mein nahi.
- 📝 Aakhri tanker rate ki jagah average rate chahiye to bataiye.

## 12b. Print reports

- ✅ **Salesman settlement report** (A4): nozzle-wise opening / closing / testing / sale litre / rate / amount,
  payment (cash, paytm, ccms, credit), credit party list (fuel udhaar + cash diya), farak (short/excess),
  manager ko jama cash, sign ki jagah (Salesman, Manager, Owner).
  Approve hote hi Settlement page par print button; purane report Reports → 🖨️ Print.
- ✅ **Din ka salesman-wise summary** (A4 landscape): har salesman ki fuel-wise litre, sale, cash, paytm, ccms,
  credit, creditor ko cash, cash jama, short/excess + kul. Sirf approved duty judti hai; pending ka naam alag likha aata hai.
  Saath mein **Creditor list**: party, salesman, gaadi/slip, fuel udhaar, cash diya — aur **party-wise jod**.
  **Creditor se payment mila (aaj)**: party, kaise (cash / bank naam / paytm / ccms), UTR, amount.
  **Din ki kul aawak**: har mode mein salesman se + creditor se = kul.
  Manager ke paas kul cash = salesman ka cash jama + creditor se mila cash.
- ✅ Report duty ki tarikh se banti hai, aur saved snapshot se (baad ke rate badlav se nahi badalti).
- ✅ Pump ka naam/pata secrets mein `PUMP_NAME`, `PUMP_ADDRESS`.

## 13. Owner extras

- ✅ Hisaab check: tank stock = register, party balance = khata, cash minus nahi.
- ✅ Backup: poora data JSON mein download.
- ✅ Audit log: kisne, kab, kya badla.
- ⏳ Reports PDF / print, WhatsApp message — abhi nahi.

---

## 13b. App ki bhasha

- ✅ App ke saare screen, button, message, error aur print report **professional English** mein.
  (Ye LOGIC.md aapke liye Hinglish mein hi hai.)
- Shabd: Duty → **Shift**, Hisaab → **Settlement**, Udhaar → **Credit sale**, Party ko cash diya → **Cash advance**,
  Galla → **Cash in hand**, Kharcha → **Expenses**, Tanker inward → **Fuel purchase**, Barabar → **Matched**.
- Kharcha categories: Salary, Electricity, Maintenance, Transport, Office, Bank charges, Rent, Miscellaneous.

## 13c. Design

- ✅ Poori app ek theme mein (teal rang): rangeen header, card jaise numbers, bade (48px) button, 16px input
  (phone par zoom nahi hota), phone par kam khali jagah.
- ✅ **Salesman screen mobile ke liye:** upar progress (Sales → Payments → Submitted); har nozzle ka apna card
  jisme seedha litre daalo; entry ke baad bada amount + Edit / Cancel; credit sale "➕ Add" / "🗑 Remove";
  "Check & submit" box hara (Matched) ya laal (Short/Excess) dikhata hai; "My Entries" tarikh-wise cards.

## 13d. Galti sudhaar — Edit / Reverse (kahan kya button)
**Usool:** paise ya stock wali entry kabhi delete nahi hoti. Galti ho to **Reverse** — aaj ki tareekh (IST) par ulti entry,
original record mein rehti hai (status "Reversed"). Sab ek hi database function (transaction) mein — aadha kaam kabhi nahi.

| Kahan | Kya | Kaun |
|---|---|---|
| Salesman sale entry | Edit / Cancel (settlement submit se pehle) | Salesman |
| Testing | 🗑 Remove — meter wapas pehle wali reading par. Sirf tab jab uske baad meter na badla ho (na closing, na doosri testing) | Manager, Owner |
| Party payment | ↩️ Reverse — party balance wapas badhega, cash/bank/Paytm/CCMS se nikal jayega | Owner |
| Cash deposit / Paytm settlement / CCMS adjust / Oil payment | ↩️ Reverse — dono taraf ulti (group_id se joda) | Owner |
| Opening balance (money) | ↩️ Reverse, phir sahi opening dobara | Owner |
| Fuel purchase (approved) | ↩️ Reverse — tank se litre kam, oil company payable kam. Wahi invoice no. dobara daal sakte | Owner |
| Dip (approved) | ↩️ Reverse — variance ulta | Owner |
| Expense (approved) | ↩️ Reverse — paisa cash/bank mein wapas | Owner |
| User | Naam, mobile, role, active, password | Owner |
| Nozzle | Naam badlo (duplicate nahi), meter correction (duty par nahi) | Owner |
| Tank | Naam, capacity (capacity < current stock nahi) | Owner |
| Bank / Oil company | Naam badlo (duplicate nahi), active/inactive | Owner |
| Fuel rate | Sirf **future** rate delete. Aaj/purana galat ho to naya rate daalo | Owner |
| Approved settlement | 🔒 Locked. Galti alag entry se sudharo (party payment, transfer, stock correction) | — |

Rok-tok:
- Ek entry do baar reverse nahi. Reversal entry ka reversal nahi.
- Reverse se Cash / Paytm / CCMS minus nahi ho sakta (pehle doosri entry theek karo).
- Sale (settlement) wali money rows Money page se reverse nahi hoti.
- Reverse ke baad consistency check (System page) saaf rehna chahiye: register = tank, party = ledger.

## 14. Code ki sakhti (v2 mein hamesha)

- ✅ Login ki chaabi (token) URL mein nahi rehti — screenshot / link share karne se login bahar nahi jata.

- ✅ Paise aur litre ke liye `Decimal` (purana app `float` use karta hai — chhoti rounding galtiyan sambhav).
- ✅ **R10 (v2):** approve ek database transaction mein (`approve_settlement_v2`) — test kiya: tank na ho to stock, credit, entries kuch nahi badla.
- ~~R10 — Approve aadha ho sakta hai:~~ purane app mein stock minus hua aur phir status save fail hua to dobara approve par stock **do baar** minus.
  v2: approve ka saara kaam ek database transaction mein — ya sab hoga, ya kuch nahi.
- ✅ Har rule ka test (neeche table). Deploy se pehle saare test pass hone chahiye.

---

## 15. v2 mein naye rules (purane app ki 3 aur galtiyan)

- ✅ **R11 — Closing se pehle nozzle free:** purane app mein duty band karte hi nozzle free ho jaata tha,
  chahe closing na hui ho → agli duty ki opening purani reading se → sale do baar gin sakti thi.
  v2: nozzle **sirf closing save hone par** free hota hai. Closing ke baad bhi galti sudhaar sakte hain,
  jab tak nozzle agli duty mein na chala jaye.
- ✅ **R12 — Manager pehle closing kare to salesman atak jaata tha:** purane app mein closing pehle hui to
  salesman hisaab bhej hi nahi pata tha. v2 mein dono kisi bhi kram mein ho sakte hain.
- ✅ **R13 — Duty ki tarikh:** purana app duty ki tarikh khud nahi daalta tha, database ka default lagta tha.
  Supabase ka default UTC hota hai, to raat 12 se 5:30 baje tak shuru hui duty pichle din ki ban sakti thi (galat rate).
  v2: tarikh hamesha India time (IST) se.
- ✅ Duty **settlement approve hone par apne aap band** hoti hai. Reopen par salesman entries sudhaar ke dobara bhej sakta hai.
- ✅ Testing max 100 L ek baar mein (galti se 1000 type na ho).
- ✅ Closing reading meter ki abhi ki reading (testing judi hui) se kam nahi ho sakti.
- ✅ Meter reading aur tank stock haath se sirf Owner sudhaar sakta hai, **kaaran ke saath**, aur har badlav `audit_log` mein.
- ✅ Approve, closing, rate, user, nozzle — har zaroori kaam `audit_log` mein.

---

## Test examples

| # | Rule | Input | Sahi jawab |
|---|------|-------|-----------|
| T1 | Testing count nahi | Opening 1000.00, Closing 1105.00, Testing 5.00 | Net sale = 100.00 L |
| T2 | Amount | 100.00 L × ₹100.00 | ₹10,000.00 |
| T3 | Purana amount fix | 1 tarikh ₹10,000 save; 5 tarikh rate ₹102 | 1 tarikh ki report = ₹10,000 |
| T4 | Nozzle ek ko | N1 salesman A ko, duty chalu; ab B ko N1 | ❌ Rok |
| T5 | Nozzle free | A ki duty band; ab B ko N1 | ✅ Allow |
| T6 | Short | Meter ₹10,000; jama ₹9,950 | Short ₹50 → approve nahi, Hold |
| T7 | ±₹2 tolerance | Meter ₹10,000; jama ₹9,998.50 | Matched → approve ho sakta hai |
| T8 | Opening auto | N1 ki pichli closing 1105.00 | Nayi duty opening = 1105.00 |
| T9 | Creditor ko cash | Cash ₹5,000, party ko diya ₹500 | Manager ko jama ₹4,500; party balance +₹500 |
| T10 | Closing < opening | Opening 1105, closing 1100 | ❌ Rok |
| T11 | Testing > gross | Gross 3 L, testing 5 L | ❌ Rok |
| T12 | Stock minus | Petrol tank 5,000 L; approve 100 L | Tank 4,900 L (sirf ek baar) |

📝 Rounding: litre 2 decimal, rupee 2 decimal (confirm baaki)

---

## Khule sawal

- [ ] **R1** Duty ke beech rate change: abhi poori duty, duty ki tarikh ke rate se. Do hisse chahiye to bataiye.
- [ ] Credit limit paar: abhi sirf warning. Rok chahiye?
- [ ] P&L laagat: aakhri tanker rate theek, ya average?
- [ ] Rounding: litre aur rupaye 2 decimal (ROUND_HALF_UP). Theek?
- [ ] Baaki: galat party sudhaar, PDF/print, WhatsApp — kab chahiye?
