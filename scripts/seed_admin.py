# scripts/seed_admin.py
import os
import sys
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Add the project root to the Python path to allow importing api modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
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
        # 1. Find the Admin role
        admin_role = db.query(Role).filter(Role.name == RoleType.ADMIN.value).first()
        if not admin_role:
            print(f"Error: Role '{RoleType.ADMIN.value}' not found in the database.")
            print("Please ensure the database schema is initialized correctly ('database/init_schema.sql').")
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
            office_id=None # Admins are not necessarily tied to an office
        )
        db.add(admin_user)
        db.commit()
        print(f"Successfully created admin user '{ADMIN_EMAIL}'.")
        print(f"IMPORTANT: Remember to change the default password if you used the default ('{ADMIN_PASSWORD}')!")

    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Attempting to seed initial admin user...")
    seed_admin() 