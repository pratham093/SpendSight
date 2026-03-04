CREATE DATABASE IF NOT EXISTS expense_tracker_db;

CREATE EXTERNAL TABLE IF NOT EXISTS expense_tracker_db.expenses (
    userid STRING,
    vendor STRING,
    amount DOUBLE,
    category STRING,
    date STRING,
    created_at STRING
)
PARTITIONED BY (
    year STRING,
    month STRING,
    day STRING
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://expense-analytics-pratham-2026/'
TBLPROPERTIES ('has_encrypted_data'='false');

MSCK REPAIR TABLE expense_tracker_db.expenses;

SELECT * FROM expense_tracker_db.expenses LIMIT 10;

SELECT
    category,
    SUM(amount) as total,
    COUNT(*) as count
FROM expense_tracker_db.expenses
WHERE year = '2026'
GROUP BY category
ORDER BY total DESC;

SELECT
    vendor,
    SUM(amount) as total_spent,
    COUNT(*) as visits
FROM expense_tracker_db.expenses
WHERE year = '2026'
GROUP BY vendor
ORDER BY total_spent DESC
LIMIT 10;

SELECT
    month,
    SUM(amount) as monthly_total
FROM expense_tracker_db.expenses
WHERE year = '2026'
GROUP BY month
ORDER BY month;
