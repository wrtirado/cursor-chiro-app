-- Companies Table: Base organizational entity
CREATE TABLE Companies (
    company_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
    -- payment_info TEXT -- To be added later (Task 9)
);

-- Offices Table: Locations belonging to companies
CREATE TABLE Offices (
    office_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES Companies(company_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    address TEXT,
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
);

-- Users Table: All system users
CREATE TABLE Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    office_id INTEGER REFERENCES Offices(office_id) ON DELETE SET NULL,
    role_id INTEGER NOT NULL REFERENCES Roles(role_id),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    join_code TEXT UNIQUE,
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
);

-- TherapyPlans Table: Treatment plans created by chiropractors
CREATE TABLE TherapyPlans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    chiropractor_id INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    version INTEGER DEFAULT 1,
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
);

-- PlanExercises Table: Exercises included in therapy plans
CREATE TABLE PlanExercises (
    plan_exercise_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES TherapyPlans(plan_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    instructions TEXT,
    sequence_order INTEGER NOT NULL,
    image_url TEXT,
    video_url TEXT,
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
);

-- PlanAssignments Table: Assignment of plans to patients
CREATE TABLE PlanAssignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES TherapyPlans(plan_id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    assigned_by_id INTEGER REFERENCES Users(user_id) ON DELETE SET NULL,
    assigned_at INTEGER DEFAULT (unixepoch()),
    start_date INTEGER, -- Store as Unix timestamp
    end_date INTEGER,   -- Store as Unix timestamp
    UNIQUE (plan_id, patient_id)
);

-- Progress Table: Patient progress tracking
CREATE TABLE Progress (
    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL REFERENCES PlanAssignments(assignment_id) ON DELETE CASCADE,
    plan_exercise_id INTEGER NOT NULL REFERENCES PlanExercises(plan_exercise_id) ON DELETE CASCADE,
    completed_at INTEGER, -- Store as Unix timestamp
    notes TEXT,
    UNIQUE (assignment_id, plan_exercise_id)
);

-- Branding Table: Company/office branding information
CREATE TABLE Branding (
    branding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    office_id INTEGER UNIQUE NOT NULL REFERENCES Offices(office_id) ON DELETE CASCADE,
    logo_url TEXT,
    colors TEXT, -- Store color theme as JSON string
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX idx_users_email ON Users(email);
CREATE INDEX idx_planassignments_patient_id ON PlanAssignments(patient_id);
CREATE INDEX idx_progress_assignment_id ON Progress(assignment_id);

-- Triggers to automatically update updated_at timestamps
CREATE TRIGGER update_companies_updated_at
AFTER UPDATE ON Companies
FOR EACH ROW
BEGIN
    UPDATE Companies SET updated_at = unixepoch() WHERE company_id = OLD.company_id;
END;

CREATE TRIGGER update_offices_updated_at
AFTER UPDATE ON Offices
FOR EACH ROW
BEGIN
    UPDATE Offices SET updated_at = unixepoch() WHERE office_id = OLD.office_id;
END;

CREATE TRIGGER update_users_updated_at
AFTER UPDATE ON Users
FOR EACH ROW
BEGIN
    UPDATE Users SET updated_at = unixepoch() WHERE user_id = OLD.user_id;
END;

CREATE TRIGGER update_therapyplans_updated_at
AFTER UPDATE ON TherapyPlans
FOR EACH ROW
BEGIN
    UPDATE TherapyPlans SET updated_at = unixepoch() WHERE plan_id = OLD.plan_id;
END;

CREATE TRIGGER update_planexercises_updated_at
AFTER UPDATE ON PlanExercises
FOR EACH ROW
BEGIN
    UPDATE PlanExercises SET updated_at = unixepoch() WHERE plan_exercise_id = OLD.plan_exercise_id;
END;

CREATE TRIGGER update_branding_updated_at
AFTER UPDATE ON Branding
FOR EACH ROW
BEGIN
    UPDATE Branding SET updated_at = unixepoch() WHERE branding_id = OLD.branding_id;
END;