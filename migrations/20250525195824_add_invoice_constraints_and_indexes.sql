-- MIGRATION: 20250525195824_add_invoice_constraints_and_indexes.sql
-- CREATED_AT: 2025-05-25T19:58:24.726038

-- UP script
-- Add indexes for performance on the invoice table
CREATE INDEX idx_invoice_office_id ON invoice(office_id);
CREATE INDEX idx_invoice_billing_period_start ON invoice(billing_period_start);
CREATE INDEX idx_invoice_status ON invoice(status);
CREATE INDEX idx_invoice_stripe_id ON invoice(stripe_invoice_id);
CREATE INDEX idx_invoice_type ON invoice(invoice_type);

-- DOWN script
-- Remove the indexes
DROP INDEX IF EXISTS idx_invoice_type;
DROP INDEX IF EXISTS idx_invoice_stripe_id;
DROP INDEX IF EXISTS idx_invoice_status;
DROP INDEX IF EXISTS idx_invoice_billing_period_start;
DROP INDEX IF EXISTS idx_invoice_office_id;

