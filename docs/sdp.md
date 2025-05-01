# Software Development Plan (SDP)

## 1. Technology Stack

- **Frontend**
  - **Web App**: React (for chiropractor interface)
  - **Mobile App**: React Native (for patient interface)
- **Backend**: FastAPI (Python) for RESTful APIs, running in a Docker container
- **Database**: PostgreSQL (Postgres) for structured data storage, running in a Docker container
- **Containerization**: Docker for building and running the API and database containers, with Docker Compose for local orchestration
- **Storage**: AWS S3 for media files (images and videos), integrated with the API container

## 2. Database Schema

Below are the key tables and their fields to support the application’s functionality:

- **Companies**

  - `id` (PK, integer)
  - `name` (string)
  - `payment_info` (string, JSON for payment gateway details)

- **Offices**

  - `id` (PK, integer)
  - `company_id` (FK to Companies, integer)
  - `name` (string)
  - `address` (string)

- **Users**

  - `id` (PK, integer)
  - `office_id` (FK to Offices, integer)
  - `role_id` (FK to Roles, integer)
  - `name` (string)
  - `email` (string, unique)
  - `password` (string, hashed)
  - `join_code` (string, unique, for chiropractors to share with patients)

- **Roles**

  - `id` (PK, integer)
  - `name` (string, e.g., "chiropractor", "office_manager", "billing", "patient")

- **TherapyPlans**

  - `id` (PK, integer)
  - `chiropractor_id` (FK to Users, integer)
  - `name` (string)
  - `description` (text)

- **PlanExercises**

  - `id` (PK, integer)
  - `plan_id` (FK to TherapyPlans, integer)
  - `exercise_details` (text)
  - `image_url` (string, nullable)
  - `video_url` (string, nullable)

- **PlanAssignments**

  - `id` (PK, integer)
  - `plan_id` (FK to TherapyPlans, integer)
  - `patient_id` (FK to Users, integer)
  - `assigned_date` (datetime)

- **Progress**

  - `id` (PK, integer)
  - `assignment_id` (FK to PlanAssignments, integer)
  - `exercise_id` (FK to PlanExercises, integer)
  - `completion_status` (boolean)
  - `completion_date` (datetime, nullable)

- **Branding**
  - `id` (PK, integer)
  - `office_id` (FK to Offices, integer)
  - `logo_url` (string)
  - `colors` (string, JSON for color codes)

**Relationships**:

- One `Company` has many `Offices`.
- One `Office` has many `Users`.
- One `User` (chiropractor) creates many `TherapyPlans`.
- One `TherapyPlan` has many `PlanExercises` and `PlanAssignments`.
- One `PlanAssignment` tracks `Progress` for a patient.

## 3. API Endpoints

The backend will expose RESTful APIs using FastAPI. Below are the key endpoints:

### 3.1 Authentication

- **POST /auth/login**
  - Request: `{ "email": string, "password": string }`
  - Response: `{ "access_token": string, "token_type": "bearer" }`
- **POST /auth/register**
  - Request: `{ "name": string, "email": string, "password": string, "role_id": integer, "office_id": integer }`
  - Response: `{ "user_id": integer }`
  - Restricted to office managers or admins.
- **POST /auth/associate**
  - Request: `{ "join_code": string }`
  - Response: `{ "chiropractor_id": integer, "office_id": integer }`
  - Links a patient to a chiropractor.

### 3.2 Account Management

- **GET /users/me**
  - Response: `{ "id": integer, "name": string, "email": string, "role": string }`
- **PUT /users/me**
  - Request: `{ "name": string, "email": string, "password": string }`
  - Response: `{ "message": "Updated successfully" }`
- **POST /branding**
  - Request: `{ "office_id": integer, "logo_url": string, "colors": object }`
  - Response: `{ "branding_id": integer }`

### 3.3 Therapy Plans

- **POST /plans**
  - Request: `{ "name": string, "description": string, "exercises": [{ "details": string, "image_url": string, "video_url": string }] }`
  - Response: `{ "plan_id": integer }`
- **GET /plans**
  - Response: `[ { "id": integer, "name": string, "description": string } ]`
  - Filters based on user role (chiropractor sees own plans, patients see assigned plans).
- **GET /plans/{id}**
  - Response: `{ "id": integer, "name": string, "description": string, "exercises": [{ "id": integer, "details": string, "image_url": string, "video_url": string }] }`
- **PUT /plans/{id}**
  - Request: `{ "name": string, "description": string, "exercises": [...] }`
  - Response: `{ "message": "Updated successfully" }`
- **DELETE /plans/{id}**
  - Response: `{ "message": "Deleted successfully" }`
- **POST /plans/{id}/assign**
  - Request: `{ "patient_ids": [integer] }`
  - Response: `{ "assignment_ids": [integer] }`

### 3.4 Progress Tracking

- **POST /progress**
  - Request: `[ { "assignment_id": integer, "exercise_id": integer, "completion_status": boolean, "completion_date": string } ]`
  - Response: `{ "message": "Progress updated" }`
- **GET /progress/{patient_id}**
  - Response: `[ { "plan_id": integer, "exercise_id": integer, "completion_status": boolean, "completion_date": string } ]`
  - Accessible to chiropractors for their patients.

## 4. System Architecture

- **Web App**: React-based SPA communicating with the FastAPI container via RESTful APIs.
- **Mobile App**: React Native app with local storage (e.g., AsyncStorage or SQLite) for offline access, syncing with the FastAPI container when online.
- **Backend**: FastAPI server running in a Docker container, handling business logic, authentication, and data management.
- **Database**: PostgreSQL running in a Docker container, with data persistence managed via Docker volumes.
- **Media Storage**: AWS S3 for hosting images and videos, with URLs stored in the database.
- **Container Orchestration**: Docker Compose manages the API and database containers, including a shared network for communication and volumes for persistence.
- **Local Notifications**: Managed in React Native using a library like `react-native-push-notification`.

**Data Flow**:

1. Chiropractor creates a plan via the web app → FastAPI container processes the request, saves to Postgres container, and uploads media to S3.
2. Patient logs into the mobile app → Fetches assigned plans via the API container → Caches locally.
3. Patient completes exercises offline → Progress stored locally → Syncs to the API container when online.

## 5. Security

- **Authentication**: JSON Web Tokens (JWT) for secure user sessions.
- **Authorization**: Role-based access control (e.g., only chiropractors can create plans).
- **Data Protection**: Encrypt sensitive data (e.g., passwords, payment info) in transit (HTTPS) and at rest (database encryption).
- **Input Validation**: Prevent injection attacks with FastAPI’s built-in validation.

## 6. Development Phases

1. **Phase 1: Backend Setup with Docker**

   - Create a Dockerfile for the FastAPI API, based on a Python image, installing dependencies from `requirements.txt`.
   - Use the official `postgres` image for the database, configured via environment variables.
   - Set up a `docker-compose.yml` file to define services for the API and database, including networks and volumes.
   - Implement FastAPI with authentication endpoints and basic user management, connecting to the database using a containerized connection string.
   - Configure Postgres with an initial schema, potentially using a manual migration step.

2. **Phase 2: Web App Core**

   - Build the React app for login, account management, and therapy plan creation.
   - (Optional) Create a Dockerfile for the web app, using Node.js and Nginx, if containerization is desired.

3. **Phase 3: Mobile App Core**

   - Develop React Native app with login, plan viewing, and offline caching.

4. **Phase 4: Notifications**

   - Add local notification scheduling in the mobile app.

5. **Phase 5: Progress Tracking**

   - Implement progress checklist and syncing in the mobile app and web app.

6. **Phase 6: Testing & Deployment**
   - Conduct testing with Dockerized services locally using Docker Compose.
   - Deploy to production using a container orchestration platform (e.g., AWS ECS, Kubernetes).

## 7. Implementation Notes

- **Offline Functionality**: Use SQLite in React Native for structured local storage of plans and progress.
- **Media Handling**: Mobile app downloads media files when online and caches them for offline use.
- **Payment Integration**: Integrate a gateway like Stripe for payment handling, with APIs for company/office-level configuration.
- **Join Code**: Generate unique codes for chiropractors in the web app, validated via the `/auth/associate` endpoint.

## 8. Deployment

- **Container Deployment**: The application will be deployed using Docker containers for the API and database.
- **Development**: Use Docker Compose to run the API and database locally, with exposed ports (e.g., 8000 for the API) for testing.
- **Production**: Deploy containers to a platform like AWS ECS or Kubernetes, ensuring scalability and reliability.
- **Configuration**: Use environment variables to configure containers for different environments (e.g., dev, staging, prod), stored securely in a `.env` file or secrets management system.
- **CI/CD**: Set up pipelines to build and push Docker images to a registry (e.g., Docker Hub, AWS ECR) and deploy them automatically.
- **Monitoring**: Utilize Docker logs for basic monitoring, with optional advanced tools like Prometheus and Grafana for production.
