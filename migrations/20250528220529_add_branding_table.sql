-- MIGRATION: 20250528220529_add_branding_table.sql
-- CREATED_AT: 2025-05-28T22:05:29.268146

-- UP script
-- Create branding table for storing office branding customization
CREATE TABLE branding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    office_id INTEGER NOT NULL,
    logo_url TEXT,
    colors_json TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (office_id) REFERENCES offices(id),
    UNIQUE (office_id)
);

-- Create index on office_id for performance
CREATE INDEX idx_branding_office_id ON branding(office_id);

-- DOWN script
-- Remove the index first, then drop the table
DROP INDEX IF EXISTS idx_branding_office_id;
DROP TABLE IF EXISTS branding;

