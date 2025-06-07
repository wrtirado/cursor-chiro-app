# Tirado Care Provider App

This project is a FastAPI-based backend for the Tirado Care Provider mobile and web applications. It uses Docker Compose for local development, libSQL (running in a local container) for the database, and MinIO for media storage.

## Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop) (with Compose)
- [Python 3.11+](https://www.python.org/) (for running scripts locally, optional)

## Quick Start (Local Development)

1. **Clone the repository:**

   ```sh
   git clone <your-repo-url>
   cd tirado-chiro-app
   ```

2. **Start the services with Docker Compose:**

   ```sh
   docker compose up --build
   ```

   This will start the API, local libSQL database, and MinIO services.

3. **Wait for the API to be up.**

   - The API should be available at [http://localhost:8000/docs](http://localhost:8000/docs) (FastAPI Swagger UI).

4. **Run first migration & seed the database with default roles:**
   The database tables are created automatically on first run, but you must seed the default roles before creating an admin user.

   Open a new terminal and run:

   ```sh
   docker compose exec api python migrate.py up
   docker compose exec api python scripts/seed_roles.py
   ```

   You should see output indicating that roles were inserted (or already exist).

5. **Seed the initial admin user:**
   After seeding roles, run:

   ```sh
   docker compose exec api python scripts/seed_admin.py
   ```

   This will create an admin user with the email and password specified in your environment variables (or defaults).

   - Default admin email: `admin@example.com`
   - Default admin password: `adminpassword`
   - **Change these in production!**

## Recent Updates

🔄 **Terminology Refactoring Completed** (June 2025)

- Successfully migrated from 'chiropractor' to 'care_provider' terminology
- Enhanced platform flexibility for diverse healthcare provider types
- Zero breaking changes to existing functionality
- See `docs/TERMINOLOGY_REFACTORING_GUIDE.md` for complete details

## Environment Variables

- You can create a `.env` file in the project root to override defaults (see `api/core/config.py` for all options).
- Common variables:
  - `DATABASE_URL` (not required for local dev; set by Docker Compose)
  - `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, etc.
  - `ADMIN_EMAIL`, `ADMIN_PASSWORD` (for seeding admin)

## Database Notes

- The app uses [libSQL](https://libsql.org/) for local development, running in a Docker container.
- Tables are created automatically from SQLAlchemy models on first run.
- **Initial data (roles, admin user) must be seeded manually as described above.**

## Troubleshooting

- If you see errors about missing roles or admin user, make sure you have run the seeding scripts in the correct order:
  1. `seed_roles.py`
  2. `seed_admin.py`
- If you change models, you may need to reset the database (delete the volume) and re-seed.
- For MinIO access, use the default credentials unless overridden in `.env` or `docker-compose.yml`.

## Useful Commands

- **Rebuild and restart everything:**
  ```sh
  docker compose up --build
  ```
- **View API logs:**
  ```sh
  docker compose logs -f api
  ```
- **Open a shell in the API container:**
  ```sh
  docker compose exec api /bin/bash
  ```

## API Documentation

- Once running, visit [http://localhost:8000/docs](http://localhost:8000/docs) for interactive API docs (Swagger UI).

---

For further questions or issues, please open an issue in this repository.
