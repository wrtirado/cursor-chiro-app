# Product Requirements Document (PRD)

## 1. Introduction

This Product Requirements Document outlines the specifications for a new web and mobile application designed for chiropractic small businesses. The purpose is to enable chiropractors to manage their practices and provide their patients with at-home remedies and therapy plans to enhance their in-office treatments. The web application targets chiropractors for administrative and planning purposes, while the mobile app is for patients to access and follow therapy plans.

- **Target Audience**: Chiropractic small businesses (web app) and their patients (mobile app).
- **Objective**: Streamline chiropractor workflows and improve patient outcomes with accessible, at-home therapy plans.

## 2. Features

### 2.1 Web Application (for Chiropractors)

- **Account Management**

  - **Payment Handling**: Process payments for services, configurable at the company or office level.
  - **User Management**: Add, edit, or remove patients associated with the chiropractor’s office.
  - **Therapy Plan Management**: Create, edit, and assign therapy plans to patients.
  - **Branding Management**: Customize the mobile app’s appearance (e.g., logo, colors) for the office or company.
  - **Chiropractor Accounts**: Manage accounts for individual chiropractors within an office.

- **Role-based Access Control**

  - **Office/Site Manager**: Oversees office accounts, chiropractors, and patient assignments.
  - **Chiropractor**: Creates and manages therapy plans, tracks patient progress.
  - **Billing**: Manages payment processing and financial records.

- **Multi-site/Office Support**
  - Hierarchical structure with a parent company overseeing multiple offices.
  - Each office has its own accounts, managers, and chiropractors.
  - Payment options: Centralized at the company level or delegated to individual offices.

### 2.2 Mobile Application (for Patients)

- **User Authentication**

  - Login and account management functionalities.
  - Patients associate with a chiropractor using a unique join code or link provided by the chiropractor.

- **Notifications**

  - Local notifications to remind patients of exercise sessions, avoiding reliance on push notification services.

- **Offline Functionality**

  - Retrieve therapy plans from the API and store them locally.
  - Display plan details (text, images, videos) without an internet connection.

- **Therapy Plans**
  - Display content: text descriptions, videos, and images (e.g., target muscles, stretch locations).
  - Interactive checklist for patients to mark completed exercises.
  - Sync progress with the server when online for chiropractor tracking.

## 3. User Stories

- **As a chiropractor**, I want to create and assign therapy plans so my patients can follow them at home.
- **As a patient**, I want reminders for my exercises so I stay on track with my therapy plan.
- **As an office manager**, I want to manage chiropractor accounts in my office to ensure smooth operations.
- **As a billing administrator**, I want to handle payments efficiently for my office or company.
- **As a patient**, I want to view my therapy plan offline so I can use it anywhere.
- **As a chiropractor**, I want to track my patients’ progress to monitor their adherence and improvement.

## 4. User Workflow Diagrams (Textual Descriptions)

### 4.1 Chiropractor Creating a Therapy Plan

1. Logs into the web app with credentials.
2. Navigates to "Therapy Plans" section.
3. Clicks "Create New Plan."
4. Enters plan details (name, description).
5. Adds exercises with text, images, and videos (uploaded or linked).
6. Saves the plan.
7. Assigns the plan to one or more patients via their profiles.

### 4.2 Patient Associating with a Chiropractor

1. Opens the mobile app.
2. Registers or logs in with credentials.
3. Enters a unique join code or clicks a link provided by the chiropractor.
4. Account links to the chiropractor’s office, granting access to assigned plans.

### 4.3 Patient Viewing and Interacting with a Therapy Plan

1. Opens the mobile app and logs in.
2. App syncs latest plans and progress if online; uses cached data if offline.
3. Views list of assigned therapy plans.
4. Selects a plan to see details (text, images, videos).
5. Marks exercises as completed in the checklist.
6. Progress syncs to the server when an internet connection is available.

### 4.4 Notification Flow

1. Patient’s therapy plan includes a schedule (e.g., "Exercise at 9 AM daily").
2. Mobile app schedules local notifications based on the plan’s schedule.
3. Notification triggers at the designated time, prompting the patient to open the app.

## 5. Non-Functional Requirements

- **Performance**: Web app loads pages in <2 seconds; mobile app syncs data in <5 seconds when online.
- **Scalability**: Support multiple offices and thousands of patients per company.
- **Usability**: Intuitive UI for non-technical chiropractors and patients.
- **Security**: Encrypted data storage and transmission; role-based access control.

## 6. Deployment Requirements

- **Containerization**: The backend API and database must be containerized using Docker to ensure consistent deployment across development, staging, and production environments.
- **API Container**: The FastAPI application should be built into a Docker image using a custom Dockerfile, encapsulating the application code and dependencies.
- **Database Container**: The PostgreSQL database should utilize the official `postgres` Docker image, configured with necessary environment variables.
- **Orchestration**: Docker Compose will be used to manage the API and database containers, including their networks and volumes, simplifying local development and testing.
- **Configuration**: Environment variables will handle sensitive information such as database credentials and AWS S3 access keys, passed to the containers at runtime.
- **Data Persistence**: Docker volumes will be employed to ensure persistent storage for the PostgreSQL database, preventing data loss between container restarts.
- **Web App Option**: While the web application (React-based) may also be containerized, this is optional and can be served separately if preferred.
