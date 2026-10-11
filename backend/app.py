
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

CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://finbuddy-frontend.onrender.com"
        ]
    }
})

# -------------------- DATABASE --------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_SSLMODE = os.environ.get("DB_SSLMODE", "require")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing from the backend environment variables."
    )


@contextmanager
def db_connection():
    conn = psycopg2.connect(
        DATABASE_URL,
        sslmode=DB_SSLMODE,
        cursor_factory=RealDictCursor,
        connect_timeout=10
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
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def today():
    return datetime.date.today().isoformat()


def money(value):
    return round(float(value or 0), 2)


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


def expense_dict(row):
    return {
        "id": row["id"],
        "category": row["category"],
        "amount": money(row["amount"]),
        "note": row["note"] or "",
        "date": row["date"].isoformat()
    }


# Initialize tables at application startup.
init_db()


# -------------------- HOME AND HEALTH --------------------

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


# -------------------- REGISTRATION --------------------

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({
            "error": "Name, email and password are required"
        }), 400

    if not isinstance(password, str) or len(password) < 6:
        return jsonify({
            "error": "Password must be at least 6 characters"
        }), 400

    try:
        income = max(0, money(data.get("income", 0)))
        age = int(data.get("age", 25))

        if not 18 <= age <= 120:
            return jsonify({"error": "Enter a valid age"}), 400

        risk = str(data.get("risk", "moderate")).lower()

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
                """, (
                    email, name, hash_pw(password),
                    income, age, risk
                ))
                created = cur.fetchone()

        if not created:
            return jsonify({
                "error": "Email already registered. Please log in."
            }), 409

        return jsonify({
            "message": "Registered successfully",
            "name": name,
            "email": email,
            "income": income,
            "age": age,
            "risk": risk
        }), 201

    except (ValueError, TypeError):
        return jsonify({
            "error": "Please enter valid income and age"
        }), 400

    except Exception:
        app.logger.exception("Registration failed")
        return jsonify({
            "error": "Registration failed. Please try again."
        }), 500


# -------------------- LOGIN --------------------

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({
            "error": "Email and password are required"
        }), 400

    if not isinstance(password, str):
        return jsonify({"error": "Invalid password"}), 400

    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, email, password_hash, income, age, risk
                    FROM users
                    WHERE LOWER(email) = %s
                """, (email,))
                user = cur.fetchone()

        if not user or user["password_hash"] != hash_pw(password):
            return jsonify({
                "error": "Invalid email or password"
            }), 401

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
        return jsonify({
            "error": "Login service is temporarily unavailable"
        }), 500


# -------------------- PROFILE --------------------

@app.route("/api/profile", methods=["GET"])
def profile():
    email = request.args.get("email", "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, email, income, age, risk, created_at
                    FROM users
                    WHERE LOWER(email) = %s
                """, (email,))
                user = cur.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        user["income"] = money(user["income"])
        user["created_at"] = (
            user["created_at"].isoformat()
            if user["created_at"] else None
        )

        return jsonify(user)

    except Exception:
        app.logger.exception("Profile loading failed")
        return jsonify({"error": "Unable to load profile"}), 500


# -------------------- EXPENSES --------------------

@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    email = request.args.get("email", "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, category, amount, note, date
                    FROM expenses
                    WHERE LOWER(email) = %s
                    ORDER BY date DESC, id DESC
                """, (email,))
                rows = cur.fetchall()

        return jsonify([expense_dict(row) for row in rows])

    except Exception:
        app.logger.exception("Expense retrieval failed")
        return jsonify({"error": "Unable to load expenses"}), 500


@app.route("/api/expenses", methods=["POST"])
def add_expense():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    category = str(data.get("category", "")).strip()
    note = str(data.get("note", ""))

    if not email or not category:
        return jsonify({
            "error": "Email and category are required"
        }), 400

    try:
        amount = money(data.get("amount"))

        if amount <= 0:
            return jsonify({
                "error": "Amount must be greater than zero"
            }), 400

        date_value = data.get("date") or today()
        datetime.date.fromisoformat(date_value)

        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO expenses (email, category, amount, note, date)
                    SELECT email, %s, %s, %s, %s
                    FROM users
                    WHERE LOWER(email) = %s
                    RETURNING id, category, amount, note, date
                """, (
                    category, amount, note, date_value, email
                ))
                row = cur.fetchone()

        if not row:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "message": "Expense added",
            "entry": expense_dict(row)
        }), 201

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount or date"}), 400

    except Exception:
        app.logger.exception("Adding expense failed")
        return jsonify({"error": "Unable to add expense"}), 500


@app.route("/api/expenses/<int:exp_id>", methods=["DELETE"])
def delete_expense(exp_id):
    email = request.args.get("email", "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM expenses
                    WHERE id = %s AND LOWER(email) = %s
                """, (exp_id, email))
                deleted = cur.rowcount

        if not deleted:
            return jsonify({"error": "Expense not found"}), 404

        return jsonify({"message": "Deleted"})

    except Exception:
        app.logger.exception("Deleting expense failed")
        return jsonify({"error": "Unable to delete expense"}), 500


@app.route("/api/expenses/summary", methods=["GET"])
def expense_summary():
    email = request.args.get("email", "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT income FROM users
                    WHERE LOWER(email) = %s
                """, (email,))
                user = cur.fetchone()

                if not user:
                    return jsonify({"error": "User not found"}), 404

                cur.execute("""
                    SELECT category, SUM(amount) AS total
                    FROM expenses
                    WHERE LOWER(email) = %s
                    GROUP BY category
                """, (email,))
                rows = cur.fetchall()

        income = money(user["income"])
        by_category = {
            row["category"]: money(row["total"])
            for row in rows
        }
        total = sum(by_category.values())
        savings = income - total
        score = (
            max(0, min(100, round(savings / income * 100)))
            if income else 0
        )

        limits = {
            "Food": 25,
            "Rent": 30,
            "Entertainment": 10,
            "Travel": 10
        }

        insights = []

        for category, amount in by_category.items():
            percent = amount / income * 100 if income else 0

            if category in limits and percent > limits[category]:
                insights.append(
                    f"You spend {percent:.0f}% on {category}. "
                    f"Recommended: at most {limits[category]}%."
                )

        return jsonify({
            "total_expenses": money(total),
            "savings": money(savings),
            "by_category": by_category,
            "financial_score": score,
            "insights": insights
        })

    except Exception:
        app.logger.exception("Expense summary failed")
        return jsonify({"error": "Unable to load expense summary"}), 500


# -------------------- TAX CALCULATOR --------------------

def calc_old_regime(income, ded_80c, ded_80d, hra, other_ded):
    taxable = max(
        0, income - ded_80c - ded_80d - hra - other_ded
    )

    tax = 0
    slabs = [
        (250000, 0),
        (250000, 0.05),
        (500000, 0.20),
        (float("inf"), 0.30)
    ]

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
    slabs = [
        (300000, 0),
        (300000, 0.05),
        (300000, 0.10),
        (300000, 0.15),
        (300000, 0.20),
        (float("inf"), 0.30)
    ]

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
    data = request.get_json(silent=True) or {}

    try:
        income = max(0, money(data.get("income", 0)))
        ded_80c = min(max(0, money(data.get("ded_80c", 0))), 150000)
        ded_80d = min(max(0, money(data.get("ded_80d", 0))), 25000)
        hra = max(0, money(data.get("hra", 0)))
        other = max(0, money(data.get("other_ded", 0)))

    except (ValueError, TypeError):
        return jsonify({"error": "Enter valid numeric values"}), 400

    old_taxable, old_tax = calc_old_regime(
        income, ded_80c, ded_80d, hra, other
    )
    new_tax = calc_new_regime(income)

    recommendation = (
        "Old Regime" if old_tax <= new_tax else "New Regime"
    )

    email = str(data.get("email", "")).strip().lower()

    try:
        if email:
            with db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO taxes (email, income, tax, regime, year)
                        SELECT email, %s, %s, %s, %s
                        FROM users WHERE LOWER(email) = %s
                    """, (
                        income,
                        min(old_tax, new_tax),
                        recommendation,
                        datetime.date.today().year,
                        email
                    ))

        return jsonify({
            "income": income,
            "old_regime": {
                "taxable_income": old_taxable,
                "tax": old_tax
            },
            "new_regime": {
                "taxable_income": income,
                "tax": new_tax
            },
            "recommendation": recommendation,
            "you_save": abs(old_tax - new_tax),
            "effective_rate_old": round(
                old_tax / income * 100, 2
            ) if income else 0,
            "effective_rate_new": round(
                new_tax / income * 100, 2
            ) if income else 0
        })

    except Exception:
        app.logger.exception("Tax calculation failed")
        return jsonify({"error": "Unable to save or calculate tax"}), 500


# -------------------- INVESTMENT PLANNER --------------------

@app.route("/api/investments/suggest", methods=["POST"])
def suggest_investments():
    data = request.get_json(silent=True) or {}

    try:
        income = max(0, money(data.get("income", 0)))
        age = int(data.get("age", 30))
        savings = max(
            0, money(data.get("savings", income * 0.2))
        )

    except (ValueError, TypeError):
        return jsonify({
            "error": "Enter valid income, age and savings"
        }), 400

    risk = str(data.get("risk", "moderate")).lower()
    email = str(data.get("email", "")).strip().lower()

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
            {"type": "Emergency Fund", "pct": 10, "return": "Varies", "reason": "Accessible emergency savings"}
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

    allocations = [
        {
            **item,
            "monthly_amount": round(savings * item["pct"] / 100)
        }
        for item in plans[risk]
    ]

    try:
        if email:
            with db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT email FROM users WHERE LOWER(email) = %s
                    """, (email,))
                    exists = cur.fetchone()

                    if exists:
                        cur.execute("""
                            DELETE FROM investments WHERE LOWER(email) = %s
                        """, (email,))

                        for item in allocations:
                            cur.execute("""
                                INSERT INTO investments (email, type, amount)
                                VALUES (%s, %s, %s)
                            """, (
                                email, item["type"], item["monthly_amount"]
                            ))

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

    except Exception:
        app.logger.exception("Investment suggestion failed")
        return jsonify({"error": "Unable to save investment plan"}), 500


# -------------------- GOVERNMENT SCHEMES --------------------

SCHEMES = [
    {
        "name": "PM Jan Dhan Yojana",
        "category": "Banking",
        "benefit": "Basic banking access; eligibility rules apply",
        "eligibility": "Eligible Indian residents",
        "income_max": 9999999,
        "url": "https://pmjdy.gov.in"
    },
    {
        "name": "Atal Pension Yojana (APY)",
        "category": "Pension",
        "benefit": "Pension scheme subject to current rules",
        "eligibility": "Check current subscriber requirements",
        "income_max": 9999999,
        "url": "https://enps.nsdl.com"
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
        "benefit": "Government savings scheme for eligible girl children",
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

    result = [
        scheme for scheme in SCHEMES
        if scheme["income_max"] >= income
    ]

    if category:
        result = [
            scheme for scheme in result
            if scheme["category"].lower() == category.lower()
        ]

    return jsonify(result)


# -------------------- CHATBOT --------------------

RESPONSES = {
    "tax": [
        "Compare available tax regimes and verify current rules before filing.",
        "Eligible deductions can affect taxable income under the applicable regime.",
        "Keep your income and investment documents ready when planning taxes."
    ],
    "invest": [
        "Choose investments based on your goals, time horizon and risk tolerance.",
        "Mutual fund and stock returns are market-linked and not guaranteed.",
        "Build an emergency fund before taking substantial investment risk."
    ],
    "budget": [
        "Track every expense and review your spending each month.",
        "Separate needs, wants and savings when creating a budget.",
        "Review recurring subscriptions and other regular costs."
    ],
    "save": [
        "Build an emergency fund for several months of essential expenses.",
        "Automating savings after payday can help build a consistent habit.",
        "Review recurring expenses to find possible savings."
    ],
    "scheme": [
        "Check official government websites for current scheme eligibility.",
        "Compare scheme requirements before applying.",
        "Use official sources to verify current benefits and terms."
    ],
    "loan": [
        "Pay EMIs on time and review the full borrowing cost before taking a loan.",
        "Compare interest rates, fees and repayment terms across lenders.",
        "Borrow according to your repayment ability."
    ],
    "default": [
        "I'm your finance assistant. Ask about tax, investment, budgeting, saving, schemes or loans.",
        "Try asking a specific question about expenses, tax planning or savings."
    ]
}


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).lower()

    if any(word in message for word in [
        "tax", "80c", "80d", "itr", "regime", "deduct"
    ]):
        key = "tax"
    elif any(word in message for word in [
        "invest", "sip", "mutual", "elss", "ppf", "nps", "stock"
    ]):
        key = "invest"
    elif any(word in message for word in [
        "budget", "expense", "spend", "track"
    ]):
        key = "budget"
    elif any(word in message for word in [
        "save", "saving", "emergency", "fund"
    ]):
        key = "save"
    elif any(word in message for word in [
        "scheme", "government", "pmjjby", "sukanya", "atal", "awas"
    ]):
        key = "scheme"
    elif any(word in message for word in [
        "loan", "emi", "cibil", "credit"
    ]):
        key = "loan"
    else:
        key = "default"

    return jsonify({"reply": random.choice(RESPONSES[key])})


# -------------------- DASHBOARD --------------------

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    email = request.args.get("email", "").strip().lower()

    if not email:
        return jsonify({
            "error": "Email is required. Please log in again."
        }), 400

    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, email, income
                    FROM users
                    WHERE LOWER(email) = %s
                """, (email,))
                user = cur.fetchone()

                if not user:
                    return jsonify({
                        "error": (
                            "Account not found in the database. "
                            "Please register or log in with your registered account."
                        )
                    }), 404

                cur.execute("""
                    SELECT id, category, amount, note, date
                    FROM expenses
                    WHERE LOWER(email) = %s
                    ORDER BY date DESC, id DESC
                """, (email,))
                expenses = cur.fetchall()

        income = money(user["income"])
        total_expenses = sum(
            money(expense["amount"]) for expense in expenses
        )
        savings = income - total_expenses

        score = (
            max(0, min(100, round(savings / income * 100)))
            if income > 0 else 0
        )

        _, estimated_tax = calc_old_regime(
            income * 12, 150000, 25000, 0, 0
        )

        by_category = {}

        for expense in expenses:
            category = expense["category"]
            by_category[category] = (
                by_category.get(category, 0)
                + money(expense["amount"])
            )

        return jsonify({
            "name": user["name"],
            "email": user["email"],
            "monthly_income": income,
            "monthly_expenses": money(total_expenses),
            "monthly_savings": money(savings),
            "financial_score": score,
            "annual_tax_estimate": estimated_tax,
            "expense_by_category": by_category,
            "recent_expenses": [
                expense_dict(expense)
                for expense in expenses[:5]
            ]
        }), 200

    except Exception:
        app.logger.exception("Dashboard loading failed")
        return jsonify({
            "error": "Unable to load your dashboard. Please try again."
        }), 500


if __name__ == "__main__":
    app.run(
        debug=False,
        port=int(os.environ.get("PORT", 5000))
    )
