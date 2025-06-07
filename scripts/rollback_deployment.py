#!/usr/bin/env python3
"""
Emergency Rollback Script for Many-to-Many Role System
Quickly revert production deployments in case of issues
Task 34.12: Production Deployment and Post-Deployment Monitoring
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add the parent directory to the path to import from api
sys.path.append(str(Path(__file__).parent.parent))

try:
    from api.database.session import SessionLocal
    from api.models.user import User
    from api.models.role import Role
    from api.models.user_role import UserRole
    from api.models.audit_log import AuditLog
    from sqlalchemy import text
except ImportError as e:
    print(f"Warning: Could not import database modules: {e}")


class EmergencyRollback:
    """Emergency rollback system for production deployments"""

    def __init__(self, config_file: str = "scripts/deployment_config.json"):
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.rollback_id = f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def setup_logging(self):
        """Setup rollback logging"""
        log_dir = Path("logs/rollback")
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"rollback_{timestamp}.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self, config_file: str) -> Dict[str, Any]:
        """Load deployment configuration"""
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config file {config_file}: {e}")
            # Return default config
            return {
                "environments": {
                    "production": {
                        "api_url": "http://localhost:8000",
                        "database_url": "sqlite:///./healthcare.db",
                    }
                }
            }

    def execute_rollback(
        self,
        environment: str,
        backup_id: Optional[str] = None,
        reason: str = "Emergency rollback",
    ) -> bool:
        """Execute emergency rollback procedure"""
        self.logger.info(f"🚨 EMERGENCY ROLLBACK INITIATED")
        self.logger.info(f"Environment: {environment}")
        self.logger.info(f"Reason: {reason}")
        self.logger.info(f"Rollback ID: {self.rollback_id}")
        self.logger.info("=" * 60)

        try:
            # Step 1: Create emergency audit log
            self.create_rollback_audit_log(environment, reason)

            # Step 2: Stop current services
            if not self.stop_services(environment):
                self.logger.error(
                    "Failed to stop services. Manual intervention required."
                )
                return False

            # Step 3: Restore database if backup provided
            if backup_id:
                if not self.restore_database(environment, backup_id):
                    self.logger.error(
                        "Database restore failed. System may be in inconsistent state."
                    )
                    return False
            else:
                self.logger.warning("No backup ID provided. Skipping database restore.")

            # Step 4: Revert to previous application version
            if not self.revert_application(environment):
                self.logger.error("Application revert failed.")
                return False

            # Step 5: Start services with previous version
            if not self.start_services(environment):
                self.logger.error("Failed to start services with previous version.")
                return False

            # Step 6: Validate rollback success
            if not self.validate_rollback(environment):
                self.logger.error("Rollback validation failed.")
                return False

            # Step 7: Create success audit log
            self.create_rollback_completion_log(environment, True)

            self.logger.info("✅ EMERGENCY ROLLBACK COMPLETED SUCCESSFULLY")
            return True

        except Exception as e:
            self.logger.error(f"💥 ROLLBACK FAILED: {e}")
            self.create_rollback_completion_log(environment, False, str(e))
            return False

    def create_rollback_audit_log(self, environment: str, reason: str):
        """Create audit log for rollback initiation"""
        try:
            db = SessionLocal()

            audit_log = AuditLog(
                user_id=None,  # System operation
                action="ROLLBACK_INITIATED",
                resource_type="DEPLOYMENT",
                resource_id=environment,
                details={
                    "rollback_id": self.rollback_id,
                    "environment": environment,
                    "reason": reason,
                    "initiated_at": datetime.now().isoformat(),
                    "initiated_by": "emergency_rollback_script",
                },
                ip_address="127.0.0.1",
                user_agent="EmergencyRollbackScript/1.0",
            )

            db.add(audit_log)
            db.commit()
            db.close()

            self.logger.info(f"Rollback audit log created")

        except Exception as e:
            self.logger.warning(f"Failed to create audit log: {e}")

    def stop_services(self, environment: str) -> bool:
        """Stop current running services"""
        self.logger.info("Stopping current services...")

        try:
            # Stop Docker services
            result = subprocess.run(
                ["docker-compose", "down", "--remove-orphans"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                self.logger.info("✅ Services stopped successfully")
                return True
            else:
                self.logger.error(f"Failed to stop services: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.logger.error("Service stop operation timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error stopping services: {e}")
            return False

    def restore_database(self, environment: str, backup_id: str) -> bool:
        """Restore database from backup"""
        self.logger.info(f"Restoring database from backup: {backup_id}")

        try:
            backup_dir = Path("database/backups")
            backup_files = list(backup_dir.glob(f"*{backup_id}*"))

            if not backup_files:
                self.logger.error(f"No backup files found for ID: {backup_id}")
                return False

            backup_file = backup_files[0]
            self.logger.info(f"Using backup file: {backup_file}")

            # Create a new backup of current state before restore
            current_backup = backup_dir / f"pre_rollback_{self.rollback_id}.db"

            if Path("database/healthcare.db").exists():
                subprocess.run(
                    ["cp", "database/healthcare.db", str(current_backup)], check=True
                )
                self.logger.info(f"Current database backed up to: {current_backup}")

            # Restore from backup
            subprocess.run(
                ["cp", str(backup_file), "database/healthcare.db"], check=True
            )

            self.logger.info("✅ Database restored successfully")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Database restore failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error during database restore: {e}")
            return False

    def revert_application(self, environment: str) -> bool:
        """Revert application to previous version"""
        self.logger.info("Reverting application to previous version...")

        try:
            # Check for previous images
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                capture_output=True,
                text=True,
            )

            images = result.stdout.strip().split("\n")
            healthcare_images = [
                img for img in images if "healthcare-app" in img and "latest" not in img
            ]

            if not healthcare_images:
                self.logger.error("No previous application images found")
                return False

            # Use the most recent non-latest image
            previous_image = healthcare_images[0]
            self.logger.info(f"Reverting to image: {previous_image}")

            # Tag as latest for docker-compose
            subprocess.run(
                ["docker", "tag", previous_image, "healthcare-app:latest"], check=True
            )

            self.logger.info("✅ Application reverted successfully")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Application revert failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error during application revert: {e}")
            return False

    def start_services(self, environment: str) -> bool:
        """Start services with reverted version"""
        self.logger.info("Starting services with reverted version...")

        try:
            # Start services
            result = subprocess.run(
                ["docker-compose", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                self.logger.info("Services started, waiting for initialization...")
                time.sleep(30)  # Wait for services to initialize

                self.logger.info("✅ Services started successfully")
                return True
            else:
                self.logger.error(f"Failed to start services: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.logger.error("Service start operation timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error starting services: {e}")
            return False

    def validate_rollback(self, environment: str) -> bool:
        """Validate that rollback was successful"""
        self.logger.info("Validating rollback success...")

        try:
            import requests

            env_config = self.config["environments"].get(environment, {})
            api_url = env_config.get("api_url", "http://localhost:8000")

            # Test basic API health
            response = requests.get(f"{api_url}/health", timeout=30)
            if response.status_code != 200:
                self.logger.error(f"API health check failed: {response.status_code}")
                return False

            # Test database connectivity
            try:
                db = SessionLocal()
                db.execute(text("SELECT 1"))

                # Check that basic role system is working
                roles_count = db.query(Role).count()
                users_count = db.query(User).count()

                self.logger.info(
                    f"Database validation: {roles_count} roles, {users_count} users"
                )

                db.close()

            except Exception as e:
                self.logger.error(f"Database validation failed: {e}")
                return False

            # Test authentication endpoint
            auth_response = requests.get(f"{api_url}/api/v1/auth/status", timeout=10)
            if auth_response.status_code != 200:
                self.logger.error(
                    f"Authentication check failed: {auth_response.status_code}"
                )
                return False

            self.logger.info("✅ Rollback validation successful")
            return True

        except Exception as e:
            self.logger.error(f"Rollback validation failed: {e}")
            return False

    def create_rollback_completion_log(
        self, environment: str, success: bool, error_message: str = None
    ):
        """Create audit log for rollback completion"""
        try:
            db = SessionLocal()

            details = {
                "rollback_id": self.rollback_id,
                "environment": environment,
                "success": success,
                "completed_at": datetime.now().isoformat(),
            }

            if error_message:
                details["error_message"] = error_message

            audit_log = AuditLog(
                user_id=None,  # System operation
                action="ROLLBACK_COMPLETED" if success else "ROLLBACK_FAILED",
                resource_type="DEPLOYMENT",
                resource_id=environment,
                details=details,
                ip_address="127.0.0.1",
                user_agent="EmergencyRollbackScript/1.0",
            )

            db.add(audit_log)
            db.commit()
            db.close()

            self.logger.info(f"Rollback completion audit log created")

        except Exception as e:
            self.logger.warning(f"Failed to create completion audit log: {e}")

    def list_available_backups(self) -> List[Dict[str, Any]]:
        """List available database backups"""
        backup_dir = Path("database/backups")

        if not backup_dir.exists():
            return []

        backups = []
        for backup_file in backup_dir.glob("*.db"):
            stat = backup_file.stat()
            backups.append(
                {
                    "filename": backup_file.name,
                    "path": str(backup_file),
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x["created"], reverse=True)
        return backups

    def quick_rollback(self, environment: str = "production") -> bool:
        """Quick rollback using the most recent backup"""
        self.logger.info("🚨 EXECUTING QUICK ROLLBACK")

        backups = self.list_available_backups()
        if not backups:
            self.logger.error("No backups available for quick rollback")
            return False

        latest_backup = backups[0]
        backup_id = latest_backup["filename"].replace(".db", "").replace("backup_", "")

        self.logger.info(f"Using latest backup: {latest_backup['filename']}")
        self.logger.info(f"Backup created: {latest_backup['created']}")

        return self.execute_rollback(
            environment=environment,
            backup_id=backup_id,
            reason="Quick rollback using latest backup",
        )

    def generate_rollback_report(self) -> Dict[str, Any]:
        """Generate a comprehensive rollback report"""
        return {
            "rollback_id": self.rollback_id,
            "timestamp": datetime.now().isoformat(),
            "available_backups": self.list_available_backups(),
            "system_status": self.get_system_status(),
            "recommended_actions": self.get_recommended_actions(),
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        try:
            # Check Docker services
            docker_result = subprocess.run(
                ["docker-compose", "ps", "--format", "json"],
                capture_output=True,
                text=True,
            )

            services_status = "unknown"
            if docker_result.returncode == 0:
                services_status = (
                    "running" if "Up" in docker_result.stdout else "stopped"
                )

            # Check database
            db_status = "unknown"
            try:
                db = SessionLocal()
                db.execute(text("SELECT 1"))
                db.close()
                db_status = "accessible"
            except:
                db_status = "inaccessible"

            return {
                "services": services_status,
                "database": db_status,
                "last_check": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"error": str(e), "last_check": datetime.now().isoformat()}

    def get_recommended_actions(self) -> List[str]:
        """Get recommended rollback actions based on current state"""
        actions = []

        system_status = self.get_system_status()

        if system_status.get("services") == "running":
            actions.append("Services are running - consider stopping before rollback")

        if system_status.get("database") == "inaccessible":
            actions.append("Database is inaccessible - prioritize database restore")

        backups = self.list_available_backups()
        if not backups:
            actions.append(
                "No backups available - create manual backup before proceeding"
            )
        elif len(backups) == 1:
            actions.append(
                "Only one backup available - consider creating additional backup"
            )

        return actions


def main():
    """Main rollback function"""
    parser = argparse.ArgumentParser(
        description="Emergency rollback for many-to-many role system"
    )
    parser.add_argument(
        "--environment", default="production", help="Target environment"
    )
    parser.add_argument("--backup-id", help="Specific backup ID to restore from")
    parser.add_argument(
        "--reason", default="Emergency rollback", help="Reason for rollback"
    )
    parser.add_argument(
        "--quick", action="store_true", help="Quick rollback using latest backup"
    )
    parser.add_argument(
        "--list-backups", action="store_true", help="List available backups"
    )
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument(
        "--config", default="scripts/deployment_config.json", help="Configuration file"
    )

    args = parser.parse_args()

    print("🚨 EMERGENCY ROLLBACK SYSTEM")
    print("=" * 40)

    try:
        rollback = EmergencyRollback(args.config)

        if args.list_backups:
            print("Available backups:")
            backups = rollback.list_available_backups()
            if not backups:
                print("No backups found")
            else:
                for backup in backups:
                    print(
                        f"  {backup['filename']} - {backup['created']} ({backup['size']} bytes)"
                    )
            return

        if args.status:
            status = rollback.get_system_status()
            print(f"System Status:")
            print(f"  Services: {status.get('services', 'unknown')}")
            print(f"  Database: {status.get('database', 'unknown')}")
            print(f"  Last Check: {status.get('last_check', 'unknown')}")

            actions = rollback.get_recommended_actions()
            if actions:
                print("\nRecommended Actions:")
                for action in actions:
                    print(f"  - {action}")
            return

        # Confirm before proceeding with rollback
        print(f"Environment: {args.environment}")
        print(f"Reason: {args.reason}")

        if not args.quick and not args.backup_id:
            print(
                "\nWarning: No backup ID specified. Only application will be reverted."
            )

        confirm = input("\nProceed with rollback? (yes/no): ").lower().strip()
        if confirm != "yes":
            print("Rollback cancelled by user")
            return

        # Execute rollback
        if args.quick:
            success = rollback.quick_rollback(args.environment)
        else:
            success = rollback.execute_rollback(
                environment=args.environment,
                backup_id=args.backup_id,
                reason=args.reason,
            )

        if success:
            print("🎉 Rollback completed successfully!")
            sys.exit(0)
        else:
            print("💥 Rollback failed! Check logs for details.")
            sys.exit(1)

    except Exception as e:
        print(f"💥 Rollback system error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
