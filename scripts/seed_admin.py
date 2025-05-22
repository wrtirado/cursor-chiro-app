# scripts/seed_admin.py
import os
import sys
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Add the project root to the Python path to allow importing api modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from api.database.session import SessionLocal
from api.models.base import User, Role
from api.core.security import get_password_hash
from api.core.config import RoleType

# Load environment variables from .env file
load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpassword")
ADMIN_NAME = "Default Admin"


def seed_admin():
    db: Session = SessionLocal()
    try:
        # 1. Find or Create the Admin role
        admin_role_name = RoleType.ADMIN.value
        admin_role = db.query(Role).filter(Role.name == admin_role_name).first()

        if not admin_role:
            print(f"Role '{admin_role_name}' not found. Creating it...")
            admin_role = Role(name=admin_role_name)
            db.add(admin_role)
            # We might need to flush to get the admin_role.role_id if it's auto-generated
            # and accessed immediately, or commit here if it's safe in the workflow.
            # For simplicity, if role_id is critical before user creation & commit, a flush might be needed.
            # However, SQLAlchemy often handles this relationship assignment correctly during commit.
            # Let's assume commit will handle it or role_id is assigned upon add for now.
            # If role_id is needed before commit, db.flush() here, then refresh admin_role.
            print(f"Role '{admin_role_name}' created.")
            # If role_id is SERIAL and assigned on commit, we must commit before creating user
            # or ensure the User object can take the Role object directly.
            # Let's commit to ensure role_id is available.
            db.commit()
            admin_role = (
                db.query(Role).filter(Role.name == admin_role_name).first()
            )  # Re-fetch to get ID
            if not admin_role:  # Should not happen if commit worked
                print(
                    f"FATAL: Failed to create or re-fetch role '{admin_role_name}'. Aborting admin seed."
                )
                return

        # 2. Check if admin user already exists
        existing_admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if existing_admin:
            print(f"Admin user with email '{ADMIN_EMAIL}' already exists.")
            return

        # 3. Create the admin user
        hashed_password = get_password_hash(ADMIN_PASSWORD)
        admin_user = User(
            email=ADMIN_EMAIL,
            name=ADMIN_NAME,
            password_hash=hashed_password,
            role_id=admin_role.role_id,
            office_id=None,  # Admins are not necessarily tied to an office
        )
        db.add(admin_user)
        db.commit()
        print(f"Successfully created admin user '{ADMIN_EMAIL}'.")
        print(
            f"IMPORTANT: Remember to change the default password if you used the default ('{ADMIN_PASSWORD}')!"
        )

    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("Attempting to seed initial admin user...")
    seed_admin()
