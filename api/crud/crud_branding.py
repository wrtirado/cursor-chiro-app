"""
CRUD operations for branding management.

This module handles database operations for office branding customization,
including logo URLs and color schemes with proper HIPAA compliance.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from api.models.base import Branding, Office
from api.schemas.branding import BrandingCreate, BrandingUpdate
from api.core.audit_logger import log_audit_event, AuditEvent
import json
import logging

logger = logging.getLogger(__name__)


class CRUDBranding:
    """CRUD operations for Branding model"""

    def get(self, db: Session, branding_id: int) -> Optional[Branding]:
        """Get branding by ID"""
        return db.query(Branding).filter(Branding.branding_id == branding_id).first()

    def get_by_office_id(self, db: Session, office_id: int) -> Optional[Branding]:
        """Get branding by office ID"""
        return db.query(Branding).filter(Branding.office_id == office_id).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[Branding]:
        """Get multiple branding records"""
        return (
            db.query(Branding)
            .order_by(desc(Branding.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, db: Session, *, obj_in: BrandingCreate, user_id: int) -> Branding:
        """Create new branding record"""
        try:
            # Check if branding already exists for this office
            existing = self.get_by_office_id(db, office_id=obj_in.office_id)
            if existing:
                raise ValueError(
                    f"Branding already exists for office {obj_in.office_id}"
                )

            # Verify office exists
            office = (
                db.query(Office).filter(Office.office_id == obj_in.office_id).first()
            )
            if not office:
                raise ValueError(f"Office {obj_in.office_id} not found")

            # Create branding record
            branding_data = obj_in.dict()

            # Convert colors dict to JSON string if provided
            if branding_data.get("colors"):
                branding_data["colors"] = json.dumps(branding_data["colors"])

            # Convert HttpUrl to string if provided
            if branding_data.get("logo_url"):
                branding_data["logo_url"] = str(branding_data["logo_url"])

            db_obj = Branding(**branding_data)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)

            # Audit logging
            log_audit_event(
                user=None,  # We don't have user object, only user_id
                event_type=AuditEvent.BRANDING_CREATED,
                outcome="SUCCESS",
                resource_type="branding",
                resource_id=db_obj.branding_id,
                details={
                    "branding_id": db_obj.branding_id,
                    "office_id": obj_in.office_id,
                    "has_logo": bool(obj_in.logo_url),
                    "has_colors": bool(obj_in.colors),
                    "user_id": user_id,
                },
            )

            logger.info(
                f"Created branding {db_obj.branding_id} for office {obj_in.office_id}"
            )
            return db_obj

        except Exception as e:
            db.rollback()
            logger.error(
                f"Failed to create branding for office {obj_in.office_id}: {e}"
            )
            raise

    def update(
        self, db: Session, *, db_obj: Branding, obj_in: BrandingUpdate, user_id: int
    ) -> Branding:
        """Update existing branding record"""
        try:
            update_data = obj_in.dict(exclude_unset=True)

            # Track what's being changed for audit
            changes = {}

            # Handle logo_url update
            if "logo_url" in update_data:
                old_logo = db_obj.logo_url
                new_logo = (
                    str(update_data["logo_url"]) if update_data["logo_url"] else None
                )
                if old_logo != new_logo:
                    changes["logo_url"] = {"old": old_logo, "new": new_logo}
                    db_obj.logo_url = new_logo

            # Handle colors update
            if "colors" in update_data:
                old_colors_json = db_obj.colors
                new_colors = update_data["colors"]
                new_colors_json = json.dumps(new_colors) if new_colors else None

                if old_colors_json != new_colors_json:
                    changes["colors"] = {
                        "old": json.loads(old_colors_json) if old_colors_json else None,
                        "new": new_colors,
                    }
                    db_obj.colors = new_colors_json

            if changes:
                db.commit()
                db.refresh(db_obj)

                # Audit logging
                log_audit_event(
                    user=None,  # We don't have user object, only user_id
                    event_type=AuditEvent.BRANDING_UPDATED,
                    outcome="SUCCESS",
                    resource_type="branding",
                    resource_id=db_obj.branding_id,
                    details={
                        "branding_id": db_obj.branding_id,
                        "office_id": db_obj.office_id,
                        "changes": changes,
                        "user_id": user_id,
                    },
                )

                logger.info(
                    f"Updated branding {db_obj.branding_id} for office {db_obj.office_id}"
                )

            return db_obj

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update branding {db_obj.branding_id}: {e}")
            raise

    def remove(
        self, db: Session, *, branding_id: int, user_id: int
    ) -> Optional[Branding]:
        """Remove branding record"""
        try:
            obj = self.get(db, branding_id=branding_id)
            if obj:
                office_id = obj.office_id
                db.delete(obj)
                db.commit()

                # Audit logging
                log_audit_event(
                    user=None,  # We don't have user object, only user_id
                    event_type=AuditEvent.BRANDING_DELETED,
                    outcome="SUCCESS",
                    resource_type="branding",
                    resource_id=branding_id,
                    details={
                        "branding_id": branding_id,
                        "office_id": office_id,
                        "user_id": user_id,
                    },
                )

                logger.info(f"Deleted branding {branding_id} for office {office_id}")
                return obj
            return None

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete branding {branding_id}: {e}")
            raise

    def create_or_update(
        self, db: Session, *, office_id: int, obj_in: BrandingUpdate, user_id: int
    ) -> Branding:
        """Create branding if it doesn't exist, or update if it does"""
        existing = self.get_by_office_id(db, office_id=office_id)

        if existing:
            return self.update(db, db_obj=existing, obj_in=obj_in, user_id=user_id)
        else:
            # Convert BrandingUpdate to BrandingCreate
            create_data = obj_in.dict(exclude_unset=True)
            create_data["office_id"] = office_id
            create_obj = BrandingCreate(**create_data)
            return self.create(db, obj_in=create_obj, user_id=user_id)

    def get_effective_branding(
        self,
        db: Session,
        office_id: int,
        default_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get effective branding for an office with fallback to defaults.
        Returns a dict with the final branding configuration.
        """
        # Default branding configuration
        if default_config is None:
            default_config = {
                "logo_url": None,
                "colors": {
                    "primary": "#007bff",
                    "secondary": "#6c757d",
                    "accent": "#17a2b8",
                    "background": "#ffffff",
                    "text": "#212529",
                },
            }

        # Get custom branding for office
        custom_branding = self.get_by_office_id(db, office_id=office_id)

        # Build effective configuration
        effective = {
            "branding_id": custom_branding.branding_id if custom_branding else None,
            "office_id": office_id,
            "logo_url": None,
            "colors": default_config["colors"].copy(),
            "has_custom_logo": False,
            "has_custom_colors": False,
            "created_at": custom_branding.created_at if custom_branding else None,
            "updated_at": custom_branding.updated_at if custom_branding else None,
        }

        if custom_branding:
            # Use custom logo if available
            if custom_branding.logo_url:
                effective["logo_url"] = custom_branding.logo_url
                effective["has_custom_logo"] = True
            else:
                effective["logo_url"] = default_config.get("logo_url")

            # Merge custom colors with defaults
            if custom_branding.colors:
                try:
                    custom_colors = json.loads(custom_branding.colors)
                    if isinstance(custom_colors, dict):
                        effective["colors"].update(custom_colors)
                        effective["has_custom_colors"] = True
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        f"Invalid colors JSON for branding {custom_branding.branding_id}"
                    )
        else:
            # Use default logo if no custom branding
            effective["logo_url"] = default_config.get("logo_url")

        return effective


# Global instance
crud_branding = CRUDBranding()
