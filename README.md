# ◈ FinPilot – Smart Financial Assistant
### A Digital CA for Middle-Class India

> A full-stack startup-level web application that helps middle-class families with
> tax planning, expense tracking, investment guidance and government scheme discovery.

---

## 📁 Project Structure

```
finpilot-project/
│
├── frontend/                  ← All HTML pages (open directly in browser)
│   ├── index.html             ← Landing page
│   ├── css/
│   │   └── style.css          ← Global stylesheet (dark luxury theme)
│   ├── js/
│   │   └── main.js            ← Shared JS utilities
│   └── pages/
│       ├── login.html         ← Login page
│       ├── register.html      ← Registration page
│       ├── dashboard.html     ← Main financial dashboard
│       ├── expenses.html      ← Expense tracker with pie chart
│       ├── tax.html           ← Tax calculator (old vs new regime)
│       ├── investments.html   ← Investment planner + SIP calculator
│       ├── schemes.html       ← Government scheme finder
│       └── chatbot.html       ← AI financial advisor chatbot
│
└── backend/                   ← Python Flask REST API
    ├── app.py                 ← Main Flask app with all routes
    ├── requirements.txt       ← Python dependencies
    └── schema.sql             ← MySQL database schema
```

---

## 🌟 Features

| Feature | Description |
|---|---|
| 📊 Dashboard | KPI cards, financial health score ring, expense pie chart |
| 💳 Expense Tracker | Add/delete expenses, category breakdown, smart insights |
| 🧾 Tax Calculator | Old vs New regime comparison with deduction inputs |
| 📈 Investment Planner | Risk-based allocation, SIP return calculator |
| 🏛️ Govt Schemes | Filter 10+ schemes by income and category |
| 🤖 AI Chatbot | Rule-based advisor with 40+ financial answers |
| 🔒 Auth System | Register/Login with session management |

---

## 🚀 How to Run

### Option A: Frontend Only (No Backend Needed)
1. Open `frontend/index.html` in any browser
2. All pages work in **demo mode** without the server
3. Expense data is saved in browser's `localStorage`
4. Tax calculator and chatbot work fully offline

### Option B: Full Stack (Frontend + Backend)

#### Step 1 – Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

#### Step 2 – Start Flask server
```bash
python app.py
```
Server runs at: `http://localhost:5000`

#### Step 3 – Open frontend
Open `frontend/index.html` in your browser.

#### Step 4 – (Optional) Setup MySQL
```bash
mysql -u root -p < backend/schema.sql
```
Then update `app.py` to use SQLAlchemy with MySQL instead of the in-memory DB.

---

## 💡 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3 (custom design system), Vanilla JS |
| Backend | Python Flask + CORS |
| Database | In-memory dict (dev) / MySQL (prod) |
| Charts | CSS conic-gradient (no library needed) |
| Auth | Session storage + SHA-256 password hashing |
| Hosting | Netlify (frontend) + Render (backend) |

---

## 📊 Key Algorithms

### Tax Calculation (Old Regime)
```
Taxable = Income - 80C(max 1.5L) - 80D(max 25K) - HRA - Other
Tax on first ₹2.5L = 0%
Tax on next ₹2.5L  = 5%
Tax on next ₹5L    = 20%
Tax above ₹10L     = 30%
```

### SIP Maturity Formula
```
FV = P × ((1+r)^n - 1) / r × (1+r)
where P = monthly SIP, r = monthly rate, n = total months
```

### Financial Health Score
```
Score = (Monthly Savings / Monthly Income) × 100
Capped at 0-100
```

---

## 🎯 Project Highlights (For Faculty)

1. **Real-world problem** – 73% Indians lack financial literacy
2. **Full-stack implementation** – HTML + CSS + JS + Python Flask
3. **Offline-capable** – Works without backend (localStorage)
4. **Responsive design** – Mobile-friendly layout
5. **Smart algorithms** – Tax calculation, SIP projection, health scoring
6. **Data visualization** – CSS-based pie charts and progress rings
7. **AI chatbot** – Rule-based knowledge base with 40+ responses
8. **Indian context** – Rupee, Indian tax slabs, Indian government schemes

---

## 🔮 Future Enhancements

- [ ] OpenAI API integration for advanced AI chatbot
- [ ] Stock market portfolio tracker (NSE/BSE API)
- [ ] Credit score analyzer
- [ ] Export financial report as PDF
- [ ] Mobile app (React Native)
- [ ] Hindi language support

---

## ⚠️ Disclaimer

FinPilot is an educational project built for academic purposes.
It is not registered with SEBI or IRDAI. Always consult a Certified
Financial Planner or Chartered Accountant for major financial decisions.

---

*Built by a BTech student | Domain: Fintech + Data Analytics*
