from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json, os, hashlib, datetime

app = Flask(__name__, static_folder='static')

CORS(app, origins=[
    "https://finbuddy-frontend.onrender.com"
])
def home():
    return jsonify({
        'app': 'FinBuddy Personal Finance Advisor',
        'status': 'running',
        'message': 'Backend API is working!'
    })

# ── In-memory DB (replace with SQLite/MySQL for production) ──────────────────
DB = {
    "users": {},        # email → {name, email, password_hash, income, age, risk}
    "expenses": {},     # email → [{category, amount, date, note}]
    "investments": {},  # email → [{type, amount, date}]
    "taxes": {},        # email → [{income, tax, regime, year}]
}

# ── HELPERS ──────────────────────────────────────────────────────────────────
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def today():
    return datetime.date.today().isoformat()

# ════════════════════════════════════════════════════════════════════════════
#  AUTH
# ════════════════════════════════════════════════════════════════════════════
@app.route('/api/register', methods=['POST'])
def register():
    d = request.json
    email = d.get('email', '').lower()
    if email in DB['users']:
        return jsonify({'error': 'Email already registered'}), 400
    DB['users'][email] = {
        'name': d['name'],
        'email': email,
        'password': hash_pw(d['password']),
        'income': float(d.get('income', 0)),
        'age': int(d.get('age', 25)),
        'risk': d.get('risk', 'moderate')
    }
    DB['expenses'][email] = []
    DB['investments'][email] = []
    DB['taxes'][email] = []
    return jsonify({'message': 'Registered successfully', 'name': d['name']})

@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    email = d.get('email', '').lower()
    user = DB['users'].get(email)
    if not user or user['password'] != hash_pw(d['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    return jsonify({'message': 'Login successful', 'name': user['name'], 'email': email})

@app.route('/api/profile', methods=['GET'])
def profile():
    email = request.args.get('email', '').lower()
    user = DB['users'].get(email)
    if not user:
        return jsonify({'error': 'Not found'}), 404
    u = dict(user)
    u.pop('password')
    return jsonify(u)

# ════════════════════════════════════════════════════════════════════════════
#  EXPENSES
# ════════════════════════════════════════════════════════════════════════════
@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    email = request.args.get('email', '').lower()
    return jsonify(DB['expenses'].get(email, []))

@app.route('/api/expenses', methods=['POST'])
def add_expense():
    d = request.json
    email = d['email'].lower()
    entry = {
        'id': len(DB['expenses'].get(email, [])) + 1,
        'category': d['category'],
        'amount': float(d['amount']),
        'note': d.get('note', ''),
        'date': d.get('date', today())
    }
    DB['expenses'].setdefault(email, []).append(entry)
    return jsonify({'message': 'Expense added', 'entry': entry})

@app.route('/api/expenses/<int:exp_id>', methods=['DELETE'])
def delete_expense(exp_id):
    email = request.args.get('email', '').lower()
    DB['expenses'][email] = [e for e in DB['expenses'].get(email, []) if e['id'] != exp_id]
    return jsonify({'message': 'Deleted'})

@app.route('/api/expenses/summary', methods=['GET'])
def expense_summary():
    email = request.args.get('email', '').lower()
    expenses = DB['expenses'].get(email, [])
    user = DB['users'].get(email, {})
    income = user.get('income', 0)

    total = sum(e['amount'] for e in expenses)
    by_cat = {}
    for e in expenses:
        by_cat[e['category']] = by_cat.get(e['category'], 0) + e['amount']

    savings = income - total
    score = max(0, min(100, int((savings / income * 100) if income else 0)))

    insights = []
    for cat, amt in by_cat.items():
        pct = (amt / income * 100) if income else 0
        limits = {'Food': 25, 'Rent': 30, 'Entertainment': 10, 'Travel': 10}
        if cat in limits and pct > limits[cat]:
            insights.append(f"You spend {pct:.0f}% on {cat}. Recommended: ≤{limits[cat]}%.")

    return jsonify({
        'total_expenses': total,
        'savings': savings,
        'by_category': by_cat,
        'financial_score': score,
        'insights': insights
    })

# ════════════════════════════════════════════════════════════════════════════
#  TAX CALCULATOR
# ════════════════════════════════════════════════════════════════════════════
def calc_old_regime(income, ded_80c, ded_80d, hra, other_ded):
    taxable = max(0, income - ded_80c - ded_80d - hra - other_ded)
    tax = 0
    slabs = [(250000, 0), (250000, 0.05), (500000, 0.20), (float('inf'), 0.30)]
    remaining = taxable
    for slab, rate in slabs:
        chunk = min(remaining, slab)
        tax += chunk * rate
        remaining -= chunk
        if remaining <= 0:
            break
    return taxable, round(tax)

def calc_new_regime(income):
    tax = 0
    slabs = [(300000, 0), (300000, 0.05), (300000, 0.10),
             (300000, 0.15), (300000, 0.20), (float('inf'), 0.30)]
    remaining = income
    for slab, rate in slabs:
        chunk = min(remaining, slab)
        tax += chunk * rate
        remaining -= chunk
        if remaining <= 0:
            break
    return round(tax)

@app.route('/api/tax/calculate', methods=['POST'])
def calculate_tax():
    d = request.json
    income = float(d.get('income', 0))
    ded_80c = min(float(d.get('ded_80c', 0)), 150000)
    ded_80d = min(float(d.get('ded_80d', 0)), 25000)
    hra = float(d.get('hra', 0))
    other = float(d.get('other_ded', 0))

    old_taxable, old_tax = calc_old_regime(income, ded_80c, ded_80d, hra, other)
    new_tax = calc_new_regime(income)

    recommendation = "Old Regime" if old_tax <= new_tax else "New Regime"
    savings = abs(old_tax - new_tax)

    return jsonify({
        'income': income,
        'old_regime': {'taxable_income': old_taxable, 'tax': old_tax},
        'new_regime': {'taxable_income': income, 'tax': new_tax},
        'recommendation': recommendation,
        'you_save': savings,
        'effective_rate_old': round(old_tax / income * 100, 2) if income else 0,
        'effective_rate_new': round(new_tax / income * 100, 2) if income else 0
    })

# ════════════════════════════════════════════════════════════════════════════
#  INVESTMENT PLANNER
# ════════════════════════════════════════════════════════════════════════════
@app.route('/api/investments/suggest', methods=['POST'])
def suggest_investments():
    d = request.json
    income = float(d.get('income', 0))
    risk = d.get('risk', 'moderate').lower()
    age = int(d.get('age', 30))
    savings = float(d.get('savings', income * 0.2))

    plans = {
        'conservative': [
            {'type': 'Fixed Deposit', 'pct': 40, 'return': '6-7%', 'reason': 'Safe guaranteed returns'},
            {'type': 'PPF', 'pct': 30, 'return': '7.1%', 'reason': 'Tax-free, government backed'},
            {'type': 'Sukanya Samriddhi / NSC', 'pct': 20, 'return': '7-8%', 'reason': 'High safety'},
            {'type': 'Liquid Mutual Fund', 'pct': 10, 'return': '5-6%', 'reason': 'Emergency liquidity'},
        ],
        'moderate': [
            {'type': 'SIP – Mutual Funds', 'pct': 35, 'return': '10-12%', 'reason': 'Wealth creation over time'},
            {'type': 'PPF', 'pct': 25, 'return': '7.1%', 'reason': 'Tax saving + safety'},
            {'type': 'Fixed Deposit', 'pct': 20, 'return': '6-7%', 'reason': 'Capital protection'},
            {'type': 'NPS', 'pct': 10, 'return': '9-10%', 'reason': 'Retirement + extra 80CCD deduction'},
            {'type': 'Emergency Fund', 'pct': 10, 'return': 'N/A', 'reason': '3-6 months expenses'},
        ],
        'aggressive': [
            {'type': 'Equity Mutual Funds / ELSS', 'pct': 50, 'return': '12-15%', 'reason': 'Maximum growth'},
            {'type': 'Direct Stocks', 'pct': 20, 'return': 'Variable', 'reason': 'High-reward plays'},
            {'type': 'SIP Flexi Cap', 'pct': 15, 'return': '12-14%', 'reason': 'Diversified equity'},
            {'type': 'PPF', 'pct': 15, 'return': '7.1%', 'reason': 'Tax-free debt cushion'},
        ]
    }

    plan = plans.get(risk, plans['moderate'])
    allocations = []
    for item in plan:
        amount = round(savings * item['pct'] / 100)
        future_10yr = round(amount * 12 * (((1 + 0.10) ** 10 - 1) / 0.10)) if 'SIP' in item['type'] or 'Equity' in item['type'] else round(amount * 12 * 10 * 1.07)
        allocations.append({**item, 'monthly_amount': amount, 'projected_10yr': future_10yr})

    return jsonify({
        'monthly_savings': savings,
        'risk_profile': risk,
        'allocations': allocations,
        'tip': f"At age {age}, {'focus on growth assets' if age < 40 else 'shift gradually to safer instruments'}."
    })

# ════════════════════════════════════════════════════════════════════════════
#  GOVERNMENT SCHEMES
# ════════════════════════════════════════════════════════════════════════════
SCHEMES = [
    {
        'name': 'PM Jan Dhan Yojana',
        'category': 'Banking',
        'benefit': 'Free savings account with ₹10,000 overdraft, ₹2L accident insurance',
        'eligibility': 'Any Indian citizen without a bank account',
        'income_max': 9999999,
        'url': 'https://pmjdy.gov.in'
    },
    {
        'name': 'Atal Pension Yojana (APY)',
        'category': 'Pension',
        'benefit': 'Guaranteed pension of ₹1000-₹5000/month after 60',
        'eligibility': 'Age 18-40, has a savings bank account',
        'income_max': 9999999,
        'url': 'https://enps.nsdl.com/eNPS/NationalPensionSystem.html'
    },
    {
        'name': 'PMJJBY – Life Insurance',
        'category': 'Insurance',
        'benefit': '₹2 lakh life cover at just ₹436/year',
        'eligibility': 'Age 18-50, savings bank account',
        'income_max': 9999999,
        'url': 'https://jansuraksha.gov.in'
    },
    {
        'name': 'PMSBY – Accident Insurance',
        'category': 'Insurance',
        'benefit': '₹2 lakh accident cover at ₹20/year',
        'eligibility': 'Age 18-70, savings bank account',
        'income_max': 9999999,
        'url': 'https://jansuraksha.gov.in'
    },
    {
        'name': 'Sukanya Samriddhi Yojana',
        'category': 'Savings',
        'benefit': '8.2% interest, fully tax-free, for girl child education/marriage',
        'eligibility': 'Parents of girl child below 10 years',
        'income_max': 9999999,
        'url': 'https://www.indiapost.gov.in/Financial/Pages/Content/Sukanya-Samridhi-Account.aspx'
    },
    {
        'name': 'PM Awas Yojana (Urban)',
        'category': 'Housing',
        'benefit': 'Interest subsidy of up to ₹2.67 lakh on home loan',
        'eligibility': 'Annual income below ₹18 lakh, no pucca house',
        'income_max': 1800000,
        'url': 'https://pmaymis.gov.in'
    },
    {
        'name': 'National Pension System (NPS)',
        'category': 'Pension',
        'benefit': 'Extra ₹50,000 tax deduction under 80CCD(1B), market-linked returns',
        'eligibility': 'Indian citizen age 18-70',
        'income_max': 9999999,
        'url': 'https://www.npscra.nsdl.co.in'
    },
    {
        'name': 'Kisan Vikas Patra',
        'category': 'Savings',
        'benefit': 'Money doubles in ~115 months at 7.5% interest',
        'eligibility': 'Any Indian adult',
        'income_max': 9999999,
        'url': 'https://www.indiapost.gov.in'
    },
]

@app.route('/api/schemes', methods=['GET'])
def get_schemes():
    income = float(request.args.get('income', 9999999))
    category = request.args.get('category', '')
    result = [s for s in SCHEMES if s['income_max'] >= income]
    if category:
        result = [s for s in result if s['category'].lower() == category.lower()]
    return jsonify(result)

# ════════════════════════════════════════════════════════════════════════════
#  AI CHATBOT
# ════════════════════════════════════════════════════════════════════════════
RESPONSES = {
    'tax': [
        "Under Section 80C you can save up to ₹1.5L by investing in PPF, ELSS, or paying LIC premium.",
        "Compare Old vs New regime using our Tax Calculator — Old regime suits if deductions > ₹3.75L.",
        "HRA exemption can significantly reduce taxable income if you pay rent.",
    ],
    'invest': [
        "Follow the 50-30-20 rule: 50% needs, 30% wants, 20% savings & investment.",
        "SIP in mutual funds with ₹2000/month for 15 years can grow to ~₹10 lakhs at 12% return.",
        "For beginners: start with ELSS (tax saving + equity growth) or index funds.",
        "PPF is the safest long-term investment — 7.1% tax-free, government guaranteed.",
    ],
    'budget': [
        "Track every expense — small leaks sink great ships! Use our Expense Tracker.",
        "Create a budget using the envelope method: label envelopes for each category.",
        "Automate your savings — set up auto-debit on salary day before spending.",
    ],
    'save': [
        "Build an emergency fund of 3-6 months of expenses before investing.",
        "Cancel unused subscriptions and redirect that money to SIPs.",
        "Cooking at home vs eating out can save ₹3,000-₹8,000/month for a family.",
    ],
    'scheme': [
        "PMJJBY gives ₹2L life cover at just ₹436/year — great for middle-class families!",
        "Sukanya Samriddhi: 8.2% tax-free for your daughter's future.",
        "APY gives guaranteed pension of ₹5000/month — enroll before age 40!",
    ],
    'loan': [
        "Maintain a CIBIL score above 750 for best loan rates. Pay EMIs on time!",
        "Avoid personal loans for consumption — use only for emergencies or education.",
        "Home loan interest is deductible under Section 24 up to ₹2L per year.",
    ],
    'default': [
        "I'm FinPilot AI 🤖. Ask me about tax saving, investment, budgeting, or government schemes!",
        "Great question! Try using specific terms like 'tax', 'SIP', 'save', 'scheme', or 'loan'.",
    ]
}

@app.route('/api/chat', methods=['POST'])
def chat():
    msg = request.json.get('message', '').lower()
    reply = None
    import random

    if any(k in msg for k in ['tax', '80c', '80d', 'itr', 'regime', 'deduct']):
        reply = random.choice(RESPONSES['tax'])
    elif any(k in msg for k in ['invest', 'sip', 'mutual', 'elss', 'ppf', 'nps', 'fd', 'stock']):
        reply = random.choice(RESPONSES['invest'])
    elif any(k in msg for k in ['budget', 'expense', 'spend', 'track']):
        reply = random.choice(RESPONSES['budget'])
    elif any(k in msg for k in ['save', 'saving', 'emergency', 'fund']):
        reply = random.choice(RESPONSES['save'])
    elif any(k in msg for k in ['scheme', 'government', 'pmjjby', 'sukanya', 'atal', 'awas']):
        reply = random.choice(RESPONSES['scheme'])
    elif any(k in msg for k in ['loan', 'emi', 'cibil', 'credit']):
        reply = random.choice(RESPONSES['loan'])
    else:
        reply = random.choice(RESPONSES['default'])

    return jsonify({'reply': reply})

# ════════════════════════════════════════════════════════════════════════════
#  DASHBOARD SUMMARY
# ════════════════════════════════════════════════════════════════════════════
@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    email = request.args.get('email', '').lower()
    user = DB['users'].get(email, {})
    income = user.get('income', 0)
    expenses = DB['expenses'].get(email, [])
    total_exp = sum(e['amount'] for e in expenses)
    savings = income - total_exp
    score = max(0, min(100, int((savings / income * 100) if income else 0)))

    # Quick tax estimate
    _, tax = calc_old_regime(income * 12, 150000, 25000, 0, 0)

    by_cat = {}
    for e in expenses:
        by_cat[e['category']] = by_cat.get(e['category'], 0) + e['amount']

    return jsonify({
        'name': user.get('name', ''),
        'monthly_income': income,
        'monthly_expenses': total_exp,
        'monthly_savings': savings,
        'financial_score': score,
        'annual_tax_estimate': tax,
        'expense_by_category': by_cat,
        'recent_expenses': expenses[-5:][::-1]
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
