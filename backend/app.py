
from flask import Flask, request, jsonify
from flask_cors import CORS
from contextlib import contextmanager
from psycopg2.extras import RealDictCursor
import psycopg2
import os
import hashlib
import datetime
import random

app = Flask(__name__)
CORS(app)

# Render PostgreSQL connection
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_SSLMODE = os.environ.get("DB_SSLMODE", "require")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing in Render Environment settings.")

def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode=os.environ.get("DB_SSLMODE", "require")
    )

@contextmanager
def db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured in Render.")

    conn = psycopg2.connect(
        DATABASE_URL,
        sslmode=DB_SSLMODE,
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()


def today():
    return datetime.date.today().isoformat()


def init_db():
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    income NUMERIC(14,2) NOT NULL DEFAULT 0,
                    age INTEGER NOT NULL DEFAULT 25,
                    risk TEXT NOT NULL DEFAULT 'moderate',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id BIGSERIAL PRIMARY KEY,
                    email TEXT NOT NULL REFERENCES users(email)
                        ON DELETE CASCADE,
                    category TEXT NOT NULL,
                    amount NUMERIC(14,2) NOT NULL,
                    note TEXT DEFAULT '',
                    date DATE NOT NULL DEFAULT CURRENT_DATE
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS investments (
                    id BIGSERIAL PRIMARY KEY,
                    email TEXT NOT NULL REFERENCES users(email)
                        ON DELETE CASCADE,
                    type TEXT NOT NULL,
                    amount NUMERIC(14,2) NOT NULL DEFAULT 0,
                    date DATE NOT NULL DEFAULT CURRENT_DATE
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS taxes (
                    id BIGSERIAL PRIMARY KEY,
                    email TEXT NOT NULL REFERENCES users(email)
                        ON DELETE CASCADE,
                    income NUMERIC(14,2) NOT NULL,
                    tax NUMERIC(14,2) NOT NULL,
                    regime TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)


def money(value):
    return round(float(value or 0), 2)


# Initialize database tables when the app starts.
# If the database is unavailable, Render logs will show the error.
init_db()


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Smart Finance System API is running",
        "health": "/api/health"
    })


@app.route("/api/health", methods=["GET"])
def health():
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS connected")
                cur.fetchone()
        return jsonify({
            "status": "healthy",
            "database": "connected"
        })
    except Exception:
        app.logger.exception("Database health check failed")
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected"
        }), 503


# -------------------- AUTHENTICATION --------------------

@app.route("/api/register", methods=["POST"])
def register():
    d = request.get_json(silent=True) or {}
    name = str(d.get("name", "")).strip()
    email = str(d.get("email", "")).strip().lower()
    password = d.get("password", "")

    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    try:
        income = max(0, money(d.get("income", 0)))
        age = int(d.get("age", 25))
        risk = str(d.get("risk", "moderate")).lower()

        if risk not in ("conservative", "moderate", "aggressive"):
            risk = "moderate"

        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users
                        (email, name, password_hash, income, age, risk)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO NOTHING
                    RETURNING email
                """, (email, name, hash_pw(password), income, age, risk))

                created = cur.fetchone()

        if not created:
            return jsonify({"error": "Email already registered"}), 409

        return jsonify({
            "message": "Registered successfully",
            "name": name,
            "email": email
        }), 201

    except (ValueError, TypeError):
        return jsonify({"error": "Please enter valid income and age"}), 400
    except Exception:
        app.logger.exception("Registration failed")
        return jsonify({"error": "Registration failed. Please try again."}), 500


@app.route("/api/login", methods=["POST"])
def login():
    d = request.get_json(silent=True) or {}
    email = str(d.get("email", "")).strip().lower()
    password = d.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, email, password_hash, income, age, risk
                    FROM users WHERE email = %s
                """, (email,))
                user = cur.fetchone()

        if not user or user["password_hash"] != hash_pw(password):
            return jsonify({"error": "Invalid email or password"}), 401

        return jsonify({
            "message": "Login successful",
            "name": user["name"],
            "email": user["email"],
            "income": money(user["income"]),
            "age": user["age"],
            "risk": user["risk"]
        })

    except Exception:
        app.logger.exception("Login failed")
        return jsonify({"error": "Login service is temporarily unavailable"}), 500


@app.route("/api/profile", methods=["GET"])
def profile():
    email = request.args.get("email", "").strip().lower()

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT name, email, income, age, risk, created_at
                FROM users WHERE email = %s
            """, (email,))
            user = cur.fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 404

    user["income"] = money(user["income"])
    user["created_at"] = (
        user["created_at"].isoformat() if user["created_at"] else None
    )
    return jsonify(user)


# -------------------- EXPENSES --------------------

def expense_dict(row):
    return {
        "id": row["id"],
        "category": row["category"],
        "amount": money(row["amount"]),
        "note": row["note"] or "",
        "date": row["date"].isoformat()
    }


@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    email = request.args.get("email", "").strip().lower()

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.id, e.category, e.amount, e.note, e.date
                FROM expenses e
                JOIN users u ON u.email = e.email
                WHERE e.email = %s
                ORDER BY e.date DESC, e.id DESC
            """, (email,))
            rows = cur.fetchall()

    return jsonify([expense_dict(row) for row in rows])


@app.route("/api/expenses", methods=["POST"])
def add_expense():
    d = request.get_json(silent=True) or {}
    email = str(d.get("email", "")).strip().lower()
    category = str(d.get("category", "")).strip()
    note = str(d.get("note", ""))
    
    try:
        amount = money(d.get("amount"))
        if amount <= 0 or not category or not email:
            return jsonify({
                "error": "Email, category and a positive amount are required"
            }), 400

        date_value = d.get("date") or today()
        datetime.date.fromisoformat(date_value)

        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO expenses (email, category, amount, note, date)
                    SELECT email, %s, %s, %s, %s
                    FROM users WHERE email = %s
                    RETURNING id, category, amount, note, date
                """, (category, amount, note, date_value, email))
                row = cur.fetchone()

        if not row:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "message": "Expense added",
            "entry": expense_dict(row)
        }), 201

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount or date"}), 400


@app.route("/api/expenses/<int:exp_id>", methods=["DELETE"])
def delete_expense(exp_id):
    email = request.args.get("email", "").strip().lower()

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM expenses
                WHERE id = %s AND email = %s
            """, (exp_id, email))
            deleted = cur.rowcount

    if not deleted:
        return jsonify({"error": "Expense not found"}), 404

    return jsonify({"message": "Deleted"})


@app.route("/api/expenses/summary", methods=["GET"])
def expense_summary():
    email = request.args.get("email", "").strip().lower()

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT income FROM users WHERE email = %s", (email,))
            user = cur.fetchone()

            if not user:
                return jsonify({"error": "User not found"}), 404

            cur.execute("""
                SELECT category, SUM(amount) AS total
                FROM expenses WHERE email = %s
                GROUP BY category
            """, (email,))
            categories = cur.fetchall()

    income = money(user["income"])
    by_cat = {r["category"]: money(r["total"]) for r in categories}
    total = sum(by_cat.values())
    savings = income - total
    score = max(0, min(100, int(savings / income * 100))) if income else 0

    limits = {"Food": 25, "Rent": 30, "Entertainment": 10, "Travel": 10}
    insights = []
    for category, amount in by_cat.items():
        percent = amount / income * 100 if income else 0
        if category in limits and percent > limits[category]:
            insights.append(
                f"You spend {percent:.0f}% on {category}. "
                f"Recommended: at most {limits[category]}%."
            )

    return jsonify({
        "total_expenses": money(total),
        "savings": money(savings),
        "by_category": by_cat,
        "financial_score": score,
        "insights": insights
    })


# -------------------- TAX CALCULATOR --------------------

def calc_old_regime(income, ded_80c, ded_80d, hra, other_ded):
    taxable = max(0, income - ded_80c - ded_80d - hra - other_ded)
    tax = 0
    slabs = [(250000, 0), (250000, 0.05), (500000, 0.20),
             (float("inf"), 0.30)]
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
             (300000, 0.15), (300000, 0.20), (float("inf"), 0.30)]
    remaining = max(0, income)

    for slab, rate in slabs:
        chunk = min(remaining, slab)
        tax += chunk * rate
        remaining -= chunk
        if remaining <= 0:
            break

    return round(tax)


@app.route("/api/tax/calculate", methods=["POST"])
def calculate_tax():
    d = request.get_json(silent=True) or {}

    try:
        income = max(0, money(d.get("income", 0)))
        ded_80c = min(max(0, money(d.get("ded_80c", 0))), 150000)
        ded_80d = min(max(0, money(d.get("ded_80d", 0))), 25000)
        hra = max(0, money(d.get("hra", 0)))
        other = max(0, money(d.get("other_ded", 0)))
    except (ValueError, TypeError):
        return jsonify({"error": "Enter valid numeric values"}), 400

    old_taxable, old_tax = calc_old_regime(
        income, ded_80c, ded_80d, hra, other
    )
    new_tax = calc_new_regime(income)
    recommendation = "Old Regime" if old_tax <= new_tax else "New Regime"

    # Save the result if an email was supplied and belongs to a registered user.
    email = str(d.get("email", "")).strip().lower()
    if email:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO taxes (email, income, tax, regime, year)
                    SELECT email, %s, %s, %s, %s
                    FROM users WHERE email = %s
                """, (
                    income, min(old_tax, new_tax), recommendation,
                    datetime.date.today().year, email
                ))

    return jsonify({
        "income": income,
        "old_regime": {"taxable_income": old_taxable, "tax": old_tax},
        "new_regime": {"taxable_income": income, "tax": new_tax},
        "recommendation": recommendation,
        "you_save": abs(old_tax - new_tax),
        "effective_rate_old": round(old_tax / income * 100, 2) if income else 0,
        "effective_rate_new": round(new_tax / income * 100, 2) if income else 0
    })


# -------------------- INVESTMENT PLANNER --------------------

@app.route("/api/investments/suggest", methods=["POST"])
def suggest_investments():
    d = request.get_json(silent=True) or {}

    try:
        income = max(0, money(d.get("income", 0)))
        age = int(d.get("age", 30))
        savings = max(0, money(d.get("savings", income * 0.2)))
    except (ValueError, TypeError):
        return jsonify({"error": "Enter valid income, age and savings"}), 400

    risk = str(d.get("risk", "moderate")).lower()
    email = str(d.get("email", "")).strip().lower()

    plans = {
        "conservative": [
            {"type": "Fixed Deposit", "pct": 40, "return": "6-7%", "reason": "Lower-risk savings"},
            {"type": "PPF", "pct": 30, "return": "Government-notified rate", "reason": "Long-term savings"},
            {"type": "NSC", "pct": 20, "return": "Government-notified rate", "reason": "Savings instrument"},
            {"type": "Liquid Mutual Fund", "pct": 10, "return": "Variable", "reason": "Liquidity; returns not guaranteed"}
        ],
        "moderate": [
            {"type": "SIP - Mutual Funds", "pct": 35, "return": "Market-linked", "reason": "Long-term growth potential"},
            {"type": "PPF", "pct": 25, "return": "Government-notified rate", "reason": "Long-term savings"},
            {"type": "Fixed Deposit", "pct": 20, "return": "Bank-specific", "reason": "Predictable interest"},
            {"type": "NPS", "pct": 10, "return": "Market-linked", "reason": "Retirement planning"},
            {"type": "Emergency Fund", "pct": 10, "return": "Varies", "reason": "Keep accessible for emergencies"}
        ],
        "aggressive": [
            {"type": "Equity Mutual Funds / ELSS", "pct": 50, "return": "Market-linked", "reason": "Higher risk and growth potential"},
            {"type": "Direct Stocks", "pct": 20, "return": "Variable", "reason": "High risk"},
            {"type": "Flexi Cap SIP", "pct": 15, "return": "Market-linked", "reason": "Equity diversification"},
            {"type": "PPF", "pct": 15, "return": "Government-notified rate", "reason": "Long-term savings"}
        ]
    }

    if risk not in plans:
        risk = "moderate"

    allocations = []
    for item in plans[risk]:
        amount = round(savings * item["pct"] / 100)
        allocations.append({**item, "monthly_amount": amount})

    if email:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT email FROM users WHERE email = %s", (email,))
                exists = cur.fetchone()
                if exists:
                    cur.execute("DELETE FROM investments WHERE email = %s", (email,))
                    for item in allocations:
                        cur.execute("""
                            INSERT INTO investments (email, type, amount)
                            VALUES (%s, %s, %s)
                        """, (email, item["type"], item["monthly_amount"]))

    return jsonify({
        "monthly_savings": savings,
        "risk_profile": risk,
        "allocations": allocations,
        "tip": (
            "Consider growth assets if you have a long time horizon."
            if age < 40 else
            "Review risk and safer assets as your goals approach."
        )
    })


# -------------------- GOVERNMENT SCHEMES --------------------

SCHEMES = [
    {
        "name": "PM Jan Dhan Yojana",
        "category": "Banking",
        "benefit": "Basic banking access; benefits depend on eligibility and current rules",
        "eligibility": "Eligible Indian residents",
        "income_max": 9999999,
        "url": "https://pmjdy.gov.in"
    },
    {
        "name": "Atal Pension Yojana (APY)",
        "category": "Pension",
        "benefit": "Pension scheme subject to current eligibility rules",
        "eligibility": "Eligible subscribers; check current rules",
        "income_max": 9999999,
        "url": "https://enps.nsdl.com/eNPS/NationalPensionSystem.html"
    },
    {
        "name": "PMJJBY - Life Insurance",
        "category": "Insurance",
        "benefit": "Life insurance subject to current scheme terms",
        "eligibility": "Check current age and bank account requirements",
        "income_max": 9999999,
        "url": "https://jansuraksha.gov.in"
    },
    {
        "name": "PMSBY - Accident Insurance",
        "category": "Insurance",
        "benefit": "Accident insurance subject to current scheme terms",
        "eligibility": "Check current age and bank account requirements",
        "income_max": 9999999,
        "url": "https://jansuraksha.gov.in"
    },
    {
        "name": "Sukanya Samriddhi Yojana",
        "category": "Savings",
        "benefit": "Government savings scheme for an eligible girl child",
        "eligibility": "Subject to current account rules",
        "income_max": 9999999,
        "url": "https://www.indiapost.gov.in"
    },
    {
        "name": "PM Awas Yojana",
        "category": "Housing",
        "benefit": "Housing assistance subject to current scheme rules",
        "eligibility": "Depends on the applicable scheme",
        "income_max": 1800000,
        "url": "https://pmaymis.gov.in"
    },
    {
        "name": "National Pension System (NPS)",
        "category": "Pension",
        "benefit": "Retirement savings with market-linked returns",
        "eligibility": "Check current subscriber rules",
        "income_max": 9999999,
        "url": "https://www.npscra.nsdl.co.in"
    },
    {
        "name": "Kisan Vikas Patra",
        "category": "Savings",
        "benefit": "Government small-savings instrument; terms may change",
        "eligibility": "Subject to current account rules",
        "income_max": 9999999,
        "url": "https://www.indiapost.gov.in"
    }
]


@app.route("/api/schemes", methods=["GET"])
def get_schemes():
    try:
        income = float(request.args.get("income", 9999999))
    except ValueError:
        return jsonify({"error": "Invalid income"}), 400

    category = request.args.get("category", "").strip()
    result = [s for s in SCHEMES if s["income_max"] >= income]

    if category:
        result = [s for s in result if s["category"].lower() == category.lower()]

    return jsonify(result)


# -------------------- CHATBOT --------------------

RESPONSES = {
    "tax": [
        "Compare the available tax regimes and verify current tax rules before filing.",
        "Eligible deductions can affect your taxable income under the applicable regime.",
        "Keep your income and investment documents ready when planning taxes."
    ],
    "invest": [
        "Choose investments based on your goals, time horizon and risk tolerance.",
        "Mutual fund and stock returns are market-linked and are not guaranteed.",
        "Build an emergency fund before taking substantial investment risk."
    ],
    "budget": [
        "Track every expense and review your spending each month.",
        "Separate needs, wants and savings when creating a budget.",
        "Review recurring subscriptions and other regular costs."
    ],
    "save": [
        "Try to build an emergency fund for several months of essential expenses.",
        "Automating savings after payday can help build a consistent habit.",
        "Review small recurring expenses to find possible savings."
    ],
    "scheme": [
        "Check official government scheme websites for current eligibility and benefits.",
        "Compare scheme requirements before applying.",
        "Use official government sources to verify current scheme terms."
    ],
    "loan": [
        "Pay EMIs on time and review the full borrowing cost before taking a loan.",
        "Compare interest rates, fees and repayment terms across lenders.",
        "Borrow according to your repayment ability."
    ],
    "default": [
        "I'm your finance assistant. Ask me about tax, investment, budgeting, saving, schemes or loans.",
        "Try asking a specific question about expenses, tax planning or savings."
    ]
}


@app.route("/api/chat", methods=["POST"])
def chat():
    d = request.get_json(silent=True) or {}
    msg = str(d.get("message", "")).lower()

    if any(k in msg for k in ["tax", "80c", "80d", "itr", "regime", "deduct"]):
        key = "tax"
    elif any(k in msg for k in ["invest", "sip", "mutual", "elss", "ppf", "nps", "stock"]):
        key = "invest"
    elif any(k in msg for k in ["budget", "expense", "spend", "track"]):
        key = "budget"
    elif any(k in msg for k in ["save", "saving", "emergency", "fund"]):
        key = "save"
    elif any(k in msg for k in ["scheme", "government", "pmjjby", "sukanya", "atal", "awas"]):
        key = "scheme"
    elif any(k in msg for k in ["loan", "emi", "cibil", "credit"]):
        key = "loan"
    else:
        key = "default"

    return jsonify({"reply": random.choice(RESPONSES[key])})


# -------------------- DASHBOARD --------------------

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    email = request.args.get("email", "").strip().lower()

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT name, income FROM users WHERE email = %s
            """, (email,))
            user = cur.fetchone()

            if not user:
                return jsonify({"error": "User not found"}), 404

            cur.execute("""
                SELECT id, category, amount, note, date
                FROM expenses WHERE email = %s
                ORDER BY date DESC, id DESC
            """, (email,))
            expenses = cur.fetchall()

    income = money(user["income"])
    total_expenses = sum(money(e["amount"]) for e in expenses)
    savings = income - total_expenses
    score = max(0, min(100, int(savings / income * 100))) if income else 0

    _, tax = calc_old_regime(income * 12, 150000, 25000, 0, 0)

    by_cat = {}
    for e in expenses:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + money(e["amount"])

    return jsonify({
        "name": user["name"],
        "monthly_income": income,
        "monthly_expenses": money(total_expenses),
        "monthly_savings": money(savings),
        "financial_score": score,
        "annual_tax_estimate": tax,
        "expense_by_category": by_cat,
        "recent_expenses": [expense_dict(e) for e in expenses[:5]]
    })


if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
