import os
import sys
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Add the project root to the Python path to allow importing api modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from api.database.session import SessionLocal
from api.models.base import Role
from api.core.config import RoleType

# Load environment variables from .env file
load_dotenv()

def seed_roles():
    db: Session = SessionLocal()
    try:
        for role in RoleType:
            existing = db.query(Role).filter(Role.name == role.value).first()
            if not existing:
                db.add(Role(name=role.value))
                print(f"Inserted role: {role.value}")
            else:
                print(f"Role already exists: {role.value}")
        db.commit()
        print("Roles seeding complete.")
    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Seeding default roles...")
    seed_roles() 