-- MIGRATION: 20250525195233_add_invoice_table.sql
-- CREATED_AT: 2025-05-25T19:52:33.541838

-- UP script
CREATE TABLE IF NOT EXISTS invoice (
    id INTEGER PRIMARY KEY,
    office_id INTEGER NOT NULL,
    billing_period_start DATETIME,
    billing_period_end DATETIME,
    total_amount_cents INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    stripe_invoice_id TEXT,
    invoice_type TEXT NOT NULL DEFAULT 'monthly',
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (office_id) REFERENCES Offices(office_id) ON DELETE CASCADE
);

-- DOWN script
DROP TABLE IF EXISTS invoice;

