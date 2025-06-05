# scripts/seed_admin.py
import os
import sys
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Add the project root to the Python path to allow importing api modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from api.database.session import SessionLocal
from api.models.base import User, Role, UserRole
from api.core.security import get_password_hash
from api.core.config import RoleType
from api.crud.crud_role import crud_user_role

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
            db.commit()
            db.refresh(admin_role)
            print(f"Role '{admin_role_name}' created with ID {admin_role.role_id}.")

        # 2. Check if admin user already exists
        existing_admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if existing_admin:
            print(f"Admin user with email '{ADMIN_EMAIL}' already exists.")

            # Check if they already have admin role
            existing_role = (
                db.query(UserRole)
                .filter(
                    UserRole.user_id == existing_admin.user_id,
                    UserRole.role_id == admin_role.role_id,
                    UserRole.is_active == True,
                )
                .first()
            )

            if not existing_role:
                print("Assigning admin role to existing user...")
                crud_user_role.assign_roles(
                    db=db,
                    user_id=existing_admin.user_id,
                    role_ids=[admin_role.role_id],
                    assigned_by_id=existing_admin.user_id,  # Self-assignment for bootstrap
                )
                print(f"Admin role assigned to existing user '{ADMIN_EMAIL}'.")
            else:
                print(f"User '{ADMIN_EMAIL}' already has admin role.")
            return

        # 3. Create the admin user (without role_id field)
        hashed_password = get_password_hash(ADMIN_PASSWORD)
        admin_user = User(
            email=ADMIN_EMAIL,
            name=ADMIN_NAME,
            password_hash=hashed_password,
            office_id=None,  # Admins are not necessarily tied to an office
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(
            f"Successfully created admin user '{ADMIN_EMAIL}' with ID {admin_user.user_id}."
        )

        # 4. Assign admin role using the many-to-many relationship
        print("Assigning admin role to new user...")
        crud_user_role.assign_roles(
            db=db,
            user_id=admin_user.user_id,
            role_ids=[admin_role.role_id],
            assigned_by_id=admin_user.user_id,  # Self-assignment for bootstrap
        )
        print(f"Admin role assigned to user '{ADMIN_EMAIL}'.")

        print(f"✅ Admin user setup complete!")
        print(f"Email: {ADMIN_EMAIL}")
        print(f"Password: {ADMIN_PASSWORD}")
        print(
            f"IMPORTANT: Remember to change the default password if you used the default!"
        )

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Setting up initial admin user...")
    seed_admin()
