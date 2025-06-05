-- MIGRATION: 20250526204248_add_invoice_line_item_table.sql
-- CREATED_AT: 2025-05-26T20:42:48.498864

-- UP script
CREATE TABLE IF NOT EXISTS invoice_line_item (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price_cents INTEGER NOT NULL DEFAULT 0,
    total_amount_cents INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (invoice_id) REFERENCES invoice(id) ON DELETE CASCADE
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_invoice_line_item_invoice_id ON invoice_line_item(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_line_item_type ON invoice_line_item(item_type);

-- DOWN script
-- Remove indexes first
DROP INDEX IF EXISTS idx_invoice_line_item_type;
DROP INDEX IF EXISTS idx_invoice_line_item_invoice_id;

-- Remove the table
DROP TABLE IF EXISTS invoice_line_item;

