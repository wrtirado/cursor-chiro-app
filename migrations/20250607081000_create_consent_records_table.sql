-- MIGRATION: 20250607081000_create_consent_records_table.sql
-- CREATED_AT: 2025-06-07T08:10:00.000000
-- DESCRIPTION: Create consent_records table for HIPAA-compliant consent tracking system

-- UP script
CREATE TABLE IF NOT EXISTS consent_records (
    consent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    consent_type TEXT NOT NULL,
    consent_version INTEGER NOT NULL DEFAULT 1,
    consent_text TEXT NOT NULL,
    purpose TEXT NOT NULL,
    scope TEXT,
    
    -- Consent status and timing
    status TEXT NOT NULL DEFAULT 'granted' CHECK (status IN ('granted', 'revoked', 'expired')),
    granted_date DATETIME NOT NULL DEFAULT (datetime('now')),
    granted_by_id INTEGER NOT NULL,
    revoked_date DATETIME,
    revoked_by_id INTEGER,
    expiry_date DATETIME,
    
    -- Third party sharing permissions
    third_party_sharing_allowed BOOLEAN NOT NULL DEFAULT 0,
    third_party_entities TEXT, -- JSON array of allowed entities
    
    -- Audit fields
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    
    -- Foreign key constraints
    FOREIGN KEY (patient_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by_id) REFERENCES Users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (revoked_by_id) REFERENCES Users(user_id) ON DELETE SET NULL
);

-- Create indexes for performance and common consent queries
CREATE INDEX IF NOT EXISTS idx_consent_records_patient_id ON consent_records(patient_id);
CREATE INDEX IF NOT EXISTS idx_consent_records_consent_type ON consent_records(consent_type);
CREATE INDEX IF NOT EXISTS idx_consent_records_status ON consent_records(status);
CREATE INDEX IF NOT EXISTS idx_consent_records_granted_date ON consent_records(granted_date);
CREATE INDEX IF NOT EXISTS idx_consent_records_expiry_date ON consent_records(expiry_date);
CREATE INDEX IF NOT EXISTS idx_consent_records_patient_type ON consent_records(patient_id, consent_type);
CREATE INDEX IF NOT EXISTS idx_consent_records_patient_status ON consent_records(patient_id, status);

-- Create a view for active consents (granted and not expired)
CREATE VIEW IF NOT EXISTS active_consent_records AS 
SELECT * FROM consent_records 
WHERE status = 'granted' 
AND (expiry_date IS NULL OR expiry_date > datetime('now'));

-- DOWN script
-- Remove the view
DROP VIEW IF EXISTS active_consent_records;

-- Remove indexes first
DROP INDEX IF EXISTS idx_consent_records_patient_status;
DROP INDEX IF EXISTS idx_consent_records_patient_type;
DROP INDEX IF EXISTS idx_consent_records_expiry_date;
DROP INDEX IF EXISTS idx_consent_records_granted_date;
DROP INDEX IF EXISTS idx_consent_records_status;
DROP INDEX IF EXISTS idx_consent_records_consent_type;
DROP INDEX IF EXISTS idx_consent_records_patient_id;

-- Remove the table
DROP TABLE IF EXISTS consent_records; 