
import os
import random
import hashlib
import hmac
import datetime
from contextlib import closing
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN",
    "https://finbuddy-frontend.onrender.com"
)

CORS(app, resources={
    r"/api/*": {"origins": [FRONTEND_ORIGIN]}
})


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg2.connect(
        database_url,
        sslmode=os.environ.get("DB_SSLMODE", "require")
    )


def query_one(sql, params=()):
    with closing(get_connection()) as conn:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return dict(row) if row else None


def query_all(sql, params=()):
    with closing(get_connection()) as conn:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]


def execute(sql, params=(), returning=False):
    with closing(get_connection()) as conn:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                row = cur.fetchone() if returning else None
                return dict(row) if row else None


def json_safe(value):
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()

    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [json_safe(v) for v in value]

    return value


def request_data():
    return request.get_json(silent=True) or {}


def today():
    return datetime.date.today().isoformat()


def get_user(email):
    return query_one(
        """SELECT user_id, name, email, password, age,
                  monthly_income, risk_appetite
           FROM users WHERE email = %s""",
        (email,)
    )


def hash_password(password):
    salt = os.urandom(16)
    iterations = 260000

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations
    )

    return (
        f"pbkdf2_sha256${iterations}$"
        f"{salt.hex()}${digest.hex()}"
    )


def verify_password(password, stored):
    # Current secure password format
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected = stored.split("$", 3)

            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt),
                int(iterations)
            ).hex()

            return hmac.compare_digest(actual, expected), None

        except (ValueError, TypeError):
            return False, None

    # Compatibility with passwords from the previous SHA-256 version.
    old_hash = hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()

    if hmac.compare_digest(old_hash, stored):
        return True, hash_password(password)

    return False, None


@app.errorhandler(Exception)
def handle_error(error):
    if isinstance(error, HTTPException):
        return error

    app.logger.exception("Backend error")
    return jsonify({
        "error": "Internal server error. Check Render logs."
    }), 500


# =========================================================
# HOME AND HEALTH CHECK
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "app": "FinBuddy Personal Finance Advisor",
        "status": "running",
        "message": "Backend API is working!"
    })


@app.route("/api/health", methods=["GET"])
def health():
    try:
        query_one("SELECT 1 AS result")

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


# =========================================================
# USER REGISTRATION
# =========================================================

@app.route("/api/register", methods=["POST"])
def register():
    data = request_data()

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name or not email or not password:
        return jsonify({
            "error": "Name, email and password are required"
        }), 400

    if len(password) < 8:
        return jsonify({
            "error": "Password must contain at least 8 characters"
        }), 400

    try:
        age = int(data.get("age", 25))
        income = float(
            data.get("income", data.get("monthly_income", 0)) or 0
        )
        risk = data.get(
            "risk", data.get("risk_appetite", "moderate")
        )

        if age < 1 or age > 120 or income < 0:
            raise ValueError()

        if risk not in ("conservative", "moderate", "aggressive"):
            return jsonify({"error": "Invalid risk profile"}), 400

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid registration details"}), 400

    try:
        user = execute(
            """INSERT INTO users
               (name, email, password, age,
                monthly_income, risk_appetite)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING user_id""",
            (
                name, email, hash_password(password),
                age, income, risk
            ),
            returning=True
        )

        return jsonify({
            "message": "Registered successfully",
            "name": name,
            "user_id": user["user_id"]
        }), 201

    except psycopg2.errors.UniqueViolation:
        return jsonify({
            "error": "Email already registered"
        }), 400


# =========================================================
# USER LOGIN
# =========================================================

@app.route("/api/login", methods=["POST"])
def login():
    data = request_data()

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    user = get_user(email)

    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    valid, upgraded_hash = verify_password(
        password, user["password"]
    )

    if not valid:
        return jsonify({"error": "Invalid credentials"}), 401

    if upgraded_hash:
        execute(
            "UPDATE users SET password = %s WHERE user_id = %s",
            (upgraded_hash, user["user_id"])
        )

    return jsonify({
        "message": "Login successful",
        "name": user["name"],
        "email": email
    })


# =========================================================
# USER PROFILE
# =========================================================

@app.route("/api/profile", methods=["GET"])
def profile():
    email = request.args.get("email", "").strip().lower()
    user = get_user(email)

    if not user:
        return jsonify({"error": "User not found"}), 404

    user.pop("password", None)

    user["income"] = float(user["monthly_income"] or 0)
    user["monthly_income"] = float(user["monthly_income"] or 0)
    user["risk"] = user["risk_appetite"]

    return jsonify(json_safe(user))


# =========================================================
# EXPENSE TRACKER
# =========================================================

@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    email = request.args.get("email", "").strip().lower()

    user = query_one(
        "SELECT user_id FROM users WHERE email = %s",
        (email,)
    )

    if not user:
        return jsonify([])

    expenses = query_all(
        """SELECT expense_id AS id, category, amount,
                  note, expense_date AS date
           FROM expenses
           WHERE user_id = %s
           ORDER BY expense_date, expense_id""",
        (user["user_id"],)
    )

    return jsonify(json_safe(expenses))


@app.route("/api/expenses", methods=["POST"])
def add_expense():
    data = request_data()

    email = str(data.get("email", "")).strip().lower()
    category = str(data.get("category", "")).strip()

    try:
        amount = float(data.get("amount"))
        expense_date = data.get("date") or today()
        datetime.date.fromisoformat(expense_date)

        if amount <= 0 or not category:
            raise ValueError()

    except (ValueError, TypeError):
        return jsonify({
            "error": "Enter a valid category, amount and date"
        }), 400

    user = query_one(
        "SELECT user_id FROM users WHERE email = %s",
        (email,)
    )

    if not user:
        return jsonify({"error": "User not found"}), 404

    expense = execute(
        """INSERT INTO expenses
           (user_id, category, amount, note, expense_date)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING expense_id AS id, category, amount,
                     note, expense_date AS date""",
        (
            user["user_id"], category, amount,
            str(data.get("note", "")), expense_date
        ),
        returning=True
    )

    return jsonify({
        "message": "Expense added",
        "entry": json_safe(expense)
    }), 201


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    email = request.args.get("email", "").strip().lower()

    user = query_one(
        "SELECT user_id FROM users WHERE email = %s",
        (email,)
    )

    if not user:
        return jsonify({"error": "User not found"}), 404

    deleted = execute(
        """DELETE FROM expenses
           WHERE expense_id = %s AND user_id = %s
           RETURNING expense_id""",
        (expense_id, user["user_id"]),
        returning=True
    )

    if not deleted:
        return jsonify({"error": "Expense not found"}), 404

    return jsonify({"message": "Deleted successfully"})


# =========================================================
# EXPENSE SUMMARY AND SAVINGS SCORE
# =========================================================

def build_expense_summary(email):
    user = query_one(
        """SELECT user_id, monthly_income
           FROM users WHERE email = %s""",
        (email,)
    )

    if not user:
        return None

    expenses = query_all(
        """SELECT category, amount FROM expenses
           WHERE user_id = %s""",
        (user["user_id"],)
    )

    income = float(user["monthly_income"] or 0)
    total = sum(float(e["amount"]) for e in expenses)

    by_category = {}

    for expense in expenses:
        category = expense["category"]
        by_category[category] = (
            by_category.get(category, 0)
            + float(expense["amount"])
        )

    savings = income - total

    score = max(
        0,
        min(100, int(savings / income * 100) if income else 0)
    )

    limits = {
        "Food": 25,
        "Rent": 30,
        "Entertainment": 10,
        "Travel": 10
    }

    insights = []

    for category, amount in by_category.items():
        percentage = amount / income * 100 if income else 0

        if category in limits and percentage > limits[category]:
            insights.append(
                f"You spend {percentage:.0f}% on {category}. "
                f"Recommended: at most {limits[category]}%."
            )

    return {
        "total_expenses": total,
        "savings": savings,
        "by_category": by_category,
        "financial_score": score,
        "insights": insights
    }


@app.route("/api/expenses/summary", methods=["GET"])
def expense_summary():
    email = request.args.get("email", "").strip().lower()
    summary = build_expense_summary(email)

    if summary is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify(json_safe(summary))


# =========================================================
# TAX CALCULATOR
# =========================================================

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
    data = request_data()

    try:
        income = max(0, float(data.get("income", 0)))
        ded_80c = min(
            max(0, float(data.get("ded_80c", 0))), 150000
        )
        ded_80d = min(
            max(0, float(data.get("ded_80d", 0))), 25000
        )
        hra = max(0, float(data.get("hra", 0)))
        other = max(0, float(data.get("other_ded", 0)))

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid tax input"}), 400

    old_taxable, old_tax = calc_old_regime(
        income, ded_80c, ded_80d, hra, other
    )

    new_tax = calc_new_regime(income)

    recommendation = (
        "Old Regime" if old_tax <= new_tax else "New Regime"
    )

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
        "effective_rate_old": (
            round(old_tax / income * 100, 2) if income else 0
        ),
        "effective_rate_new": (
            round(new_tax / income * 100, 2) if income else 0
        )
    })


# =========================================================
# INVESTMENT PLANNER
# =========================================================

@app.route("/api/investments/suggest", methods=["POST"])
def suggest_investments():
    data = request_data()

    try:
        income = max(0, float(data.get("income", 0)))
        risk = str(data.get("risk", "moderate")).lower()
        age = int(data.get("age", 30))
        savings = max(
            0, float(data.get("savings", income * 0.2))
        )

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid investment input"}), 400

    plans = {
        "conservative": [
            {
                "type": "Fixed Deposit", "pct": 40,
                "return": "6-7%",
                "reason": "Lower-risk savings option"
            },
            {
                "type": "PPF", "pct": 30,
                "return": "Government-set rate",
                "reason": "Long-term savings"
            },
            {
                "type": "Sukanya Samriddhi / NSC", "pct": 20,
                "return": "Variable",
                "reason": "Government small-savings options"
            },
            {
                "type": "Liquid Mutual Fund", "pct": 10,
                "return": "Market-linked",
                "reason": "Liquidity"
            }
        ],

        "moderate": [
            {
                "type": "SIP – Mutual Funds", "pct": 35,
                "return": "Market-linked",
                "reason": "Long-term wealth creation"
            },
            {
                "type": "PPF", "pct": 25,
                "return": "Government-set rate",
                "reason": "Long-term savings"
            },
            {
                "type": "Fixed Deposit", "pct": 20,
                "return": "Bank-specific",
                "reason": "Capital protection subject to terms"
            },
            {
                "type": "NPS", "pct": 10,
                "return": "Market-linked",
                "reason": "Retirement planning"
            },
            {
                "type": "Emergency Fund", "pct": 10,
                "return": "Not applicable",
                "reason": "Emergency expenses"
            }
        ],

        "aggressive": [
            {
                "type": "Equity Mutual Funds / ELSS", "pct": 50,
                "return": "Market-linked",
                "reason": "Long-term growth potential"
            },
            {
                "type": "Direct Stocks", "pct": 20,
                "return": "Variable",
                "reason": "Higher risk"
            },
            {
                "type": "SIP Flexi Cap", "pct": 15,
                "return": "Market-linked",
                "reason": "Diversified equity exposure"
            },
            {
                "type": "PPF", "pct": 15,
                "return": "Government-set rate",
                "reason": "Long-term savings"
            }
        ]
    }

    plan = plans.get(risk, plans["moderate"])
    allocations = []

    for item in plan:
        amount = round(savings * item["pct"] / 100)

        allocations.append({
            **item,
            "monthly_amount": amount,
            "projected_10yr": None
        })

    return jsonify({
        "monthly_savings": savings,
        "risk_profile": risk,
        "allocations": allocations,
        "tip": (
            "Focus on growth assets"
            if age < 40
            else "Consider balancing growth and lower-risk assets"
        ),
        "note": "Investment returns are not guaranteed."
    })


# =========================================================
# GOVERNMENT SCHEMES
# =========================================================

SCHEMES = [
    {
        "name": "PM Jan Dhan Yojana",
        "category": "Banking",
        "benefit": "Basic bank account and eligible scheme benefits",
        "eligibility": "Subject to official scheme rules",
        "income_max": 9999999,
        "url": "https://pmjdy.gov.in"
    },
    {
        "name": "Atal Pension Yojana (APY)",
        "category": "Pension",
        "benefit": "Pension scheme subject to contribution and eligibility",
        "eligibility": "Generally eligible subscribers aged 18-40",
        "income_max": 9999999,
        "url": "https://www.npscra.nsdl.co.in"
    },
    {
        "name": "PMJJBY – Life Insurance",
        "category": "Insurance",
        "benefit": "Life insurance subject to current scheme terms",
        "eligibility": "Eligible account holders aged 18-50",
        "income_max": 9999999,
        "url": "https://jansuraksha.gov.in"
    },
    {
        "name": "PMSBY – Accident Insurance",
        "category": "Insurance",
        "benefit": "Accident insurance subject to current scheme terms",
        "eligibility": "Eligible account holders aged 18-70",
        "income_max": 9999999,
        "url": "https://jansuraksha.gov.in"
    },
    {
        "name": "Sukanya Samriddhi Yojana",
        "category": "Savings",
        "benefit": "Government small-savings scheme for eligible girl children",
        "eligibility": "Subject to current India Post rules",
        "income_max": 9999999,
        "url": "https://www.indiapost.gov.in"
    },
    {
        "name": "PM Awas Yojana (Urban)",
        "category": "Housing",
        "benefit": "Housing assistance subject to current scheme rules",
        "eligibility": "Subject to active scheme criteria",
        "income_max": 1800000,
        "url": "https://pmaymis.gov.in"
    },
    {
        "name": "National Pension System (NPS)",
        "category": "Pension",
        "benefit": "Retirement savings subject to scheme and tax rules",
        "eligibility": "Subject to current NPS rules",
        "income_max": 9999999,
        "url": "https://www.npscra.nsdl.co.in"
    },
    {
        "name": "Kisan Vikas Patra",
        "category": "Savings",
        "benefit": "Government small-savings certificate",
        "eligibility": "Subject to current India Post rules",
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

    category = request.args.get("category", "")

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


# =========================================================
# FINANCIAL CHATBOT
# =========================================================

RESPONSES = {
    "tax": [
        "Eligible investments and payments may qualify for deductions under the old tax regime.",
        "Compare both tax regimes based on your income and eligible deductions.",
        "HRA exemption may apply when you meet the relevant conditions."
    ],

    "invest": [
        "Plan your investments based on your goals, time horizon and risk tolerance.",
        "SIP returns depend on market performance and are not guaranteed.",
        "Understand the risks and fees before investing in mutual funds.",
        "Consider an emergency fund before investing money you may need soon."
    ],

    "budget": [
        "Track your expenses and review your spending every month.",
        "Separate essential expenses from wants when creating your budget.",
        "Set a realistic monthly savings target."
    ],

    "save": [
        "Consider building an emergency fund for essential expenses.",
        "Review unused subscriptions and recurring costs.",
        "Compare your planned spending with your actual expenses."
    ],

    "scheme": [
        "Check the official scheme website for current eligibility and benefits.",
        "Government scheme terms can change, so verify details before applying."
    ],

    "loan": [
        "Pay EMIs on time and review your credit report regularly.",
        "Compare interest rates, fees and total repayment costs before borrowing.",
        "Choose loan repayments that fit your monthly budget."
    ]
}


@app.route("/api/chat", methods=["POST"])
def chat():
    message = str(
        request_data().get("message", "")
    ).lower()

    if any(word in message for word in [
        "tax", "80c", "80d", "itr", "regime", "deduct"
    ]):
        group = "tax"

    elif any(word in message for word in [
        "invest", "sip", "mutual", "elss", "ppf",
        "nps", "fd", "stock"
    ]):
        group = "invest"

    elif any(word in message for word in [
        "budget", "expense", "spend", "track"
    ]):
        group = "budget"

    elif any(word in message for word in [
        "save", "saving", "emergency", "fund"
    ]):
        group = "save"

    elif any(word in message for word in [
        "scheme", "government", "pmjjby",
        "sukanya", "atal", "awas"
    ]):
        group = "scheme"

    elif any(word in message for word in [
        "loan", "emi", "cibil", "credit"
    ]):
        group = "loan"

    else:
        return jsonify({
            "reply": (
                "I'm FinPilot AI. Ask me about tax, investments, "
                "budgeting, saving, loans or government schemes!"
            )
        })

    return jsonify({
        "reply": random.choice(RESPONSES[group])
    })


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    email = request.args.get("email", "").strip().lower()

    user = query_one(
        """SELECT user_id, name, monthly_income
           FROM users WHERE email = %s""",
        (email,)
    )

    if not user:
        return jsonify({"error": "User not found"}), 404

    expenses = query_all(
        """SELECT expense_id AS id, category, amount,
                  note, expense_date AS date
           FROM expenses
           WHERE user_id = %s
           ORDER BY expense_date, expense_id""",
        (user["user_id"],)
    )

    income = float(user["monthly_income"] or 0)

    total_expenses = sum(
        float(expense["amount"]) for expense in expenses
    )

    savings = income - total_expenses

    score = max(
        0,
        min(100, int(savings / income * 100) if income else 0)
    )

    _, estimated_tax = calc_old_regime(
        income * 12, 150000, 25000, 0, 0
    )

    by_category = {}

    for expense in expenses:
        category = expense["category"]

        by_category[category] = (
            by_category.get(category, 0)
            + float(expense["amount"])
        )

    return jsonify(json_safe({
        "name": user["name"],
        "monthly_income": income,
        "monthly_expenses": total_expenses,
        "monthly_savings": savings,
        "financial_score": score,
        "annual_tax_estimate": estimated_tax,
        "expense_by_category": by_category,
        "recent_expenses": list(reversed(expenses[-5:]))
    }))


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False
    )
