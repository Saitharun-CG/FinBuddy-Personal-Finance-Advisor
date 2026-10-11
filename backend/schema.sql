-- FinPilot Database Schema
-- Run this in MySQL Workbench or phpMyAdmin

CREATE DATABASE IF NOT EXISTS finpilot;
USE finpilot;

-- USERS TABLE
CREATE TABLE users (
  user_id     INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(100) NOT NULL,
  email       VARCHAR(150) NOT NULL UNIQUE,
  password    VARCHAR(256) NOT NULL,        -- SHA-256 hash
  age         INT DEFAULT 25,
  monthly_income DECIMAL(12,2) DEFAULT 0,
  risk_appetite  ENUM('conservative','moderate','aggressive') DEFAULT 'moderate',
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSES TABLE
CREATE TABLE expenses (
  expense_id  INT AUTO_INCREMENT PRIMARY KEY,
  user_id     INT NOT NULL,
  category    VARCHAR(50) NOT NULL,
  amount      DECIMAL(10,2) NOT NULL,
  note        VARCHAR(255),
  expense_date DATE NOT NULL,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- INVESTMENTS TABLE
CREATE TABLE investments (
  investment_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,
  type          VARCHAR(100) NOT NULL,   -- SIP, PPF, FD, etc.
  amount        DECIMAL(10,2) NOT NULL,  -- monthly amount
  return_rate   DECIMAL(5,2),
  start_date    DATE,
  notes         VARCHAR(255),
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- TAX RECORDS TABLE
CREATE TABLE tax_records (
  tax_id        INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,
  financial_year VARCHAR(10) NOT NULL,   -- e.g., '2024-25'
  annual_income  DECIMAL(12,2),
  ded_80c        DECIMAL(10,2) DEFAULT 0,
  ded_80d        DECIMAL(10,2) DEFAULT 0,
  hra_amount     DECIMAL(10,2) DEFAULT 0,
  other_ded      DECIMAL(10,2) DEFAULT 0,
  old_regime_tax DECIMAL(10,2),
  new_regime_tax DECIMAL(10,2),
  recommended    ENUM('old','new'),
  created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- CHAT HISTORY TABLE (optional)
CREATE TABLE chat_history (
  chat_id    INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  message    TEXT NOT NULL,
  reply      TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- SAMPLE DATA
INSERT INTO users (name, email, password, age, monthly_income, risk_appetite)
VALUES ('Demo User', 'demo@finpilot.in', 'demo_hash', 28, 50000, 'moderate');

INSERT INTO expenses (user_id, category, amount, note, expense_date) VALUES
(1, 'Rent',          12000, 'Monthly rent', '2025-01-01'),
(1, 'Food',          8000,  'Groceries + restaurants', '2025-01-15'),
(1, 'Travel',        3500,  'Petrol + cabs', '2025-01-20'),
(1, 'Entertainment', 2500,  'OTT + movies', '2025-01-22'),
(1, 'Health',        1500,  'Pharmacy', '2025-01-25');
