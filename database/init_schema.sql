-- database/init_schema.sql

-- Companies Table: Base organizational entity
CREATE TABLE Companies (
    company_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    -- payment_info JSONB -- To be added later (Task 9)
);

-- Offices Table: Locations belonging to companies
CREATE TABLE Offices (
    office_id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES Companies(company_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Roles Table: User role definitions
CREATE TABLE Roles (
    role_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL -- e.g., 'patient', 'chiropractor', 'office_manager', 'billing_admin'
);

-- Seed default roles
INSERT INTO Roles (name) VALUES ('patient'), ('chiropractor'), ('office_manager'), ('billing_admin'), ('admin');

-- Users Table: All system users
CREATE TABLE Users (
    user_id SERIAL PRIMARY KEY,
    office_id INT REFERENCES Offices(office_id) ON DELETE SET NULL, -- Nullable if user is not associated with a specific office initially
    role_id INT NOT NULL REFERENCES Roles(role_id),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    join_code VARCHAR(10) UNIQUE, -- For patient association
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- TherapyPlans Table: Treatment plans created by chiropractors
CREATE TABLE TherapyPlans (
    plan_id SERIAL PRIMARY KEY,
    chiropractor_id INT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE, -- Assuming chiropractors create plans
    title VARCHAR(255) NOT NULL,
    description TEXT,
    version INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- PlanExercises Table: Exercises included in therapy plans
CREATE TABLE PlanExercises (
    plan_exercise_id SERIAL PRIMARY KEY,
    plan_id INT NOT NULL REFERENCES TherapyPlans(plan_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    instructions TEXT,
    sequence_order INT NOT NULL,
    image_url VARCHAR(1024), -- To be populated via S3 integration (Task 7)
    video_url VARCHAR(1024), -- To be populated via S3 integration (Task 7)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- PlanAssignments Table: Assignment of plans to patients
CREATE TABLE PlanAssignments (
    assignment_id SERIAL PRIMARY KEY,
    plan_id INT NOT NULL REFERENCES TherapyPlans(plan_id) ON DELETE CASCADE,
    patient_id INT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE, -- Assuming patients are users
    assigned_by_id INT REFERENCES Users(user_id) ON DELETE SET NULL, -- User who assigned the plan
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    start_date DATE,
    end_date DATE,
    UNIQUE (plan_id, patient_id) -- Prevent assigning the same plan multiple times to the same patient
);

-- Progress Table: Patient progress tracking
CREATE TABLE Progress (
    progress_id SERIAL PRIMARY KEY,
    assignment_id INT NOT NULL REFERENCES PlanAssignments(assignment_id) ON DELETE CASCADE,
    plan_exercise_id INT NOT NULL REFERENCES PlanExercises(plan_exercise_id) ON DELETE CASCADE,
    completed_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    UNIQUE (assignment_id, plan_exercise_id) -- Ensure one progress entry per exercise assignment
);

-- Branding Table: Company/office branding information
CREATE TABLE Branding (
    branding_id SERIAL PRIMARY KEY,
    office_id INT UNIQUE NOT NULL REFERENCES Offices(office_id) ON DELETE CASCADE, -- Assuming branding is per office
    logo_url VARCHAR(1024),
    colors JSONB, -- Store color theme as JSON
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common lookups
CREATE INDEX idx_users_email ON Users(email);
CREATE INDEX idx_planassignments_patient_id ON PlanAssignments(patient_id);
CREATE INDEX idx_progress_assignment_id ON Progress(assignment_id);

-- Function to automatically update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply the trigger to tables with updated_at column
CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON Companies FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_offices_updated_at BEFORE UPDATE ON Offices FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON Users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_therapyplans_updated_at BEFORE UPDATE ON TherapyPlans FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_planexercises_updated_at BEFORE UPDATE ON PlanExercises FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_branding_updated_at BEFORE UPDATE ON Branding FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); 