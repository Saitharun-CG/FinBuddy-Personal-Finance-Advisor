
-- FinPilot / FinBuddy PostgreSQL Database Schema

CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password VARCHAR(256) NOT NULL,
    age INTEGER DEFAULT 25,
    monthly_income NUMERIC(12,2) DEFAULT 0,
    risk_appetite VARCHAR(20) DEFAULT 'moderate'
        CHECK (risk_appetite IN ('conservative', 'moderate', 'aggressive')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expenses (
    expense_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    amount NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    note VARCHAR(255),
    expense_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_date
ON expenses(user_id, expense_date);

CREATE TABLE IF NOT EXISTS investments (
    investment_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    type VARCHAR(100) NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    return_rate NUMERIC(5,2),
    start_date DATE,
    notes VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tax_records (
    tax_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    financial_year VARCHAR(10) NOT NULL,
    annual_income NUMERIC(12,2),
    ded_80c NUMERIC(10,2) DEFAULT 0,
    ded_80d NUMERIC(10,2) DEFAULT 0,
    hra_amount NUMERIC(10,2) DEFAULT 0,
    other_ded NUMERIC(10,2) DEFAULT 0,
    old_regime_tax NUMERIC(10,2),
    new_regime_tax NUMERIC(10,2),
    recommended VARCHAR(10)
        CHECK (recommended IN ('old', 'new')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_history (
    chat_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    reply TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
