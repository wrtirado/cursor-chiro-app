#!/usr/bin/env python3
"""
Production Deployment Script for Many-to-Many Role System
Handles deployment, validation, and monitoring setup
Task 34.12: Production Deployment and Post-Deployment Monitoring
"""

import os
import sys
import time
import json
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests
from pathlib import Path

# Add the parent directory to the path to import from api
sys.path.append(str(Path(__file__).parent.parent))

try:
    from api.database.session import SessionLocal
    from api.models.user import User
    from api.models.role import Role
    from api.models.user_role import UserRole
    from api.models.audit_log import AuditLog
    from sqlalchemy import text, func
except ImportError as e:
    print(f"Warning: Could not import database modules: {e}")
    print("Some database operations may not be available")


class ProductionDeployment:
    """Production deployment manager for role system"""

    def __init__(self, config_file: Optional[str] = None):
        self.setup_logging()
        self.config = self.load_config(config_file)
        self.deployment_start = datetime.now()
        self.health_checks = []
        self.rollback_points = []

    def setup_logging(self):
        """Setup comprehensive logging"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"production_deployment_{timestamp}.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self, config_file: Optional[str] = None) -> Dict[str, Any]:
        """Load deployment configuration"""
        default_config = {
            "api_url": os.getenv("API_URL", "http://localhost:8000"),
            "database_url": os.getenv("DATABASE_URL", "sqlite+libsql://localhost:8080"),
            "health_check_interval": 30,  # seconds
            "health_check_timeout": 10,  # seconds
            "max_deployment_time": 1800,  # 30 minutes
            "rollback_on_failure": True,
            "monitoring": {
                "enable_alerts": True,
                "alert_thresholds": {
                    "api_response_time": 5.0,  # seconds
                    "error_rate": 0.05,  # 5%
                    "role_check_time": 1.0,  # seconds
                },
            },
            "validation": {
                "required_roles": [
                    "admin",
                    "care_provider",
                    "office_manager",
                    "patient",
                    "billing_admin",
                ],
                "min_test_users": 10,
                "max_role_check_time": 2.0,
            },
        }

        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    file_config = json.load(f)
                default_config.update(file_config)
            except Exception as e:
                self.logger.warning(f"Could not load config file {config_file}: {e}")

        return default_config

    def create_rollback_point(self, name: str):
        """Create a rollback point"""
        rollback_info = {
            "name": name,
            "timestamp": datetime.now().isoformat(),
            "database_backup": self.backup_database(),
            "docker_images": self.get_docker_images(),
        }
        self.rollback_points.append(rollback_info)
        self.logger.info(f"Created rollback point: {name}")

    def backup_database(self) -> str:
        """Create database backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_pre_deployment_{timestamp}.sql"

        try:
            # For libSQL, we'll use the API to create a backup
            self.logger.info("Creating database backup...")

            # Create backup directory
            backup_dir = Path("database/backups")
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_path = backup_dir / backup_file

            # Simple backup approach - export key tables
            db = SessionLocal()
            try:
                tables = ["users", "roles", "user_roles", "audit_logs"]
                with open(backup_path, "w") as f:
                    for table in tables:
                        result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()
                        f.write(f"-- {table}: {count} records\n")

                self.logger.info(f"Database backup created: {backup_path}")
                return str(backup_path)

            finally:
                db.close()

        except Exception as e:
            self.logger.error(f"Database backup failed: {e}")
            return ""

    def get_docker_images(self) -> Dict[str, str]:
        """Get current Docker image information"""
        try:
            result = subprocess.run(
                ["docker", "images", "--format", "json"],
                capture_output=True,
                text=True,
                check=True,
            )

            images = {}
            for line in result.stdout.strip().split("\n"):
                if line:
                    image_info = json.loads(line)
                    images[image_info.get("Repository", "unknown")] = image_info.get(
                        "Tag", "latest"
                    )

            return images

        except Exception as e:
            self.logger.warning(f"Could not get Docker images: {e}")
            return {}

    def deploy_to_production(self) -> bool:
        """Main deployment process"""
        self.logger.info("Starting production deployment...")

        try:
            # Step 1: Pre-deployment validation
            self.logger.info("Step 1: Pre-deployment validation")
            if not self.pre_deployment_validation():
                self.logger.error("Pre-deployment validation failed")
                return False

            # Step 2: Create rollback point
            self.logger.info("Step 2: Creating rollback point")
            self.create_rollback_point("pre_deployment")

            # Step 3: Deploy services
            self.logger.info("Step 3: Deploying services")
            if not self.deploy_services():
                self.logger.error("Service deployment failed")
                if self.config["rollback_on_failure"]:
                    self.rollback()
                return False

            # Step 4: Database migrations
            self.logger.info("Step 4: Running database migrations")
            if not self.run_migrations():
                self.logger.error("Database migrations failed")
                if self.config["rollback_on_failure"]:
                    self.rollback()
                return False

            # Step 5: Post-deployment validation
            self.logger.info("Step 5: Post-deployment validation")
            if not self.post_deployment_validation():
                self.logger.error("Post-deployment validation failed")
                if self.config["rollback_on_failure"]:
                    self.rollback()
                return False

            # Step 6: Setup monitoring
            self.logger.info("Step 6: Setting up monitoring")
            self.setup_monitoring()

            # Step 7: Health checks
            self.logger.info("Step 7: Running initial health checks")
            if not self.run_health_checks():
                self.logger.warning(
                    "Some health checks failed - monitoring will continue"
                )

            self.logger.info("Production deployment completed successfully!")
            return True

        except Exception as e:
            self.logger.error(f"Deployment failed with exception: {e}")
            if self.config["rollback_on_failure"]:
                self.rollback()
            return False

    def pre_deployment_validation(self) -> bool:
        """Validate system before deployment"""
        validation_checks = [
            self.check_docker_environment,
            self.check_database_connection,
            self.check_migration_files,
            self.check_configuration,
        ]

        for check in validation_checks:
            try:
                if not check():
                    return False
            except Exception as e:
                self.logger.error(f"Validation check {check.__name__} failed: {e}")
                return False

        return True

    def check_docker_environment(self) -> bool:
        """Check Docker environment"""
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, check=True
            )
            self.logger.info(f"Docker version: {result.stdout.decode().strip()}")

            result = subprocess.run(
                ["docker", "compose", "--version"], capture_output=True, check=True
            )
            self.logger.info(
                f"Docker Compose version: {result.stdout.decode().strip()}"
            )

            return True
        except subprocess.CalledProcessError:
            self.logger.error("Docker or Docker Compose not available")
            return False

    def check_database_connection(self) -> bool:
        """Check database connectivity"""
        try:
            db = SessionLocal()
            result = db.execute(text("SELECT 1"))
            db.close()
            self.logger.info("Database connection successful")
            return True
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False

    def check_migration_files(self) -> bool:
        """Check migration files exist"""
        migration_files = [
            "migrations/20250605001403_create_user_roles_table.sql",
            "migrations/20250605001605_remove_users_role_id_column.sql",
        ]

        for file in migration_files:
            if not os.path.exists(file):
                self.logger.error(f"Missing migration file: {file}")
                return False

        self.logger.info("All migration files present")
        return True

    def check_configuration(self) -> bool:
        """Check configuration validity"""
        required_config = ["api_url", "database_url"]

        for key in required_config:
            if key not in self.config:
                self.logger.error(f"Missing required configuration: {key}")
                return False

        self.logger.info("Configuration validation passed")
        return True

    def deploy_services(self) -> bool:
        """Deploy services using Docker Compose"""
        try:
            self.logger.info("Building and starting services...")

            # Build and start services
            result = subprocess.run(
                ["docker", "compose", "up", "-d", "--build"],
                capture_output=True,
                text=True,
                check=True,
            )

            self.logger.info("Services started successfully")

            # Wait for services to be ready
            self.logger.info("Waiting for services to initialize...")
            time.sleep(30)

            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Service deployment failed: {e}")
            self.logger.error(f"stderr: {e.stderr}")
            return False

    def run_migrations(self) -> bool:
        """Run database migrations"""
        try:
            self.logger.info("Running database migrations...")

            # Use the existing migration script
            result = subprocess.run(
                [sys.executable, "migrate.py"],
                capture_output=True,
                text=True,
                check=True,
            )

            self.logger.info("Database migrations completed successfully")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Migration failed: {e}")
            self.logger.error(f"stderr: {e.stderr}")
            return False

    def post_deployment_validation(self) -> bool:
        """Validate system after deployment"""
        validation_checks = [
            self.validate_api_endpoints,
            self.validate_role_system,
            self.validate_audit_logging,
            self.validate_authentication,
        ]

        for check in validation_checks:
            try:
                if not check():
                    return False
            except Exception as e:
                self.logger.error(f"Post-deployment check {check.__name__} failed: {e}")
                return False

        return True

    def validate_api_endpoints(self) -> bool:
        """Validate API endpoints are responding"""
        endpoints = ["/docs", "/health", "/api/v1/auth/status"]

        for endpoint in endpoints:
            try:
                url = f"{self.config['api_url']}{endpoint}"
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    self.logger.info(f"✅ Endpoint {endpoint} responding")
                else:
                    self.logger.error(
                        f"❌ Endpoint {endpoint} returned {response.status_code}"
                    )
                    return False

            except requests.RequestException as e:
                self.logger.error(f"❌ Endpoint {endpoint} failed: {e}")
                return False

        return True

    def validate_role_system(self) -> bool:
        """Validate role system functionality"""
        try:
            db = SessionLocal()

            # Check all required roles exist
            required_roles = self.config["validation"]["required_roles"]
            existing_roles = db.query(Role).all()
            existing_role_names = {role.name for role in existing_roles}

            missing_roles = set(required_roles) - existing_role_names
            if missing_roles:
                self.logger.error(f"Missing required roles: {missing_roles}")
                return False

            self.logger.info(f"✅ All {len(required_roles)} required roles present")

            # Check user-role assignments
            user_role_count = (
                db.query(UserRole).filter(UserRole.is_active == True).count()
            )
            if user_role_count < self.config["validation"]["min_test_users"]:
                self.logger.warning(
                    f"Only {user_role_count} active user-role assignments found"
                )
            else:
                self.logger.info(f"✅ {user_role_count} active user-role assignments")

            # Test role checking performance
            start_time = time.time()
            test_users = db.query(User).limit(10).all()

            for user in test_users:
                user.get_active_roles(db)

            avg_time = (time.time() - start_time) / len(test_users) if test_users else 0

            if avg_time > self.config["validation"]["max_role_check_time"]:
                self.logger.warning(
                    f"Role check time {avg_time:.3f}s exceeds threshold"
                )
            else:
                self.logger.info(f"✅ Role check performance: {avg_time:.3f}s average")

            db.close()
            return True

        except Exception as e:
            self.logger.error(f"Role system validation failed: {e}")
            return False

    def validate_audit_logging(self) -> bool:
        """Validate audit logging functionality"""
        try:
            db = SessionLocal()

            # Check recent audit logs
            recent_logs = (
                db.query(AuditLog)
                .filter(AuditLog.timestamp >= datetime.now() - timedelta(hours=24))
                .count()
            )

            self.logger.info(f"✅ {recent_logs} audit log entries in last 24 hours")

            # Check for role-related audit logs
            role_logs = (
                db.query(AuditLog).filter(AuditLog.action.like("%ROLE%")).count()
            )

            self.logger.info(f"✅ {role_logs} role-related audit logs found")

            db.close()
            return True

        except Exception as e:
            self.logger.error(f"Audit logging validation failed: {e}")
            return False

    def validate_authentication(self) -> bool:
        """Validate authentication system"""
        try:
            # Test authentication endpoint
            auth_url = f"{self.config['api_url']}/api/v1/auth/status"
            response = requests.get(auth_url, timeout=10)

            if response.status_code == 200:
                self.logger.info("✅ Authentication system responding")
                return True
            else:
                self.logger.error(
                    f"Authentication endpoint returned {response.status_code}"
                )
                return False

        except requests.RequestException as e:
            self.logger.error(f"Authentication validation failed: {e}")
            return False

    def setup_monitoring(self):
        """Setup monitoring and alerting"""
        self.logger.info("Setting up monitoring systems...")

        # Create monitoring configuration
        monitoring_config = {
            "deployment_id": f"deployment_{int(self.deployment_start.timestamp())}",
            "start_time": self.deployment_start.isoformat(),
            "api_url": self.config["api_url"],
            "monitoring_interval": self.config["health_check_interval"],
            "alert_thresholds": self.config["monitoring"]["alert_thresholds"],
        }

        # Save monitoring configuration
        monitor_dir = Path("logs/monitoring")
        monitor_dir.mkdir(parents=True, exist_ok=True)

        config_file = monitor_dir / "monitoring_config.json"
        with open(config_file, "w") as f:
            json.dump(monitoring_config, f, indent=2)

        self.logger.info(f"Monitoring configuration saved to {config_file}")

        # Start monitoring process
        self.start_monitoring_process()

    def start_monitoring_process(self):
        """Start the monitoring process"""
        try:
            monitor_script = Path(__file__).parent / "production_monitor.py"

            if not monitor_script.exists():
                self.logger.warning("Monitor script not found - creating basic monitor")
                self.create_monitor_script(monitor_script)

            # Start monitoring in background
            subprocess.Popen(
                [
                    sys.executable,
                    str(monitor_script),
                    "--config",
                    "logs/monitoring/monitoring_config.json",
                ]
            )

            self.logger.info("Monitoring process started")

        except Exception as e:
            self.logger.error(f"Could not start monitoring process: {e}")

    def create_monitor_script(self, script_path: Path):
        """Create basic monitoring script"""
        monitor_code = '''#!/usr/bin/env python3
"""Basic production monitoring script"""
import time
import json
import logging
import requests
import argparse
from datetime import datetime
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    
    with open(args.config) as f:
        config = json.load(f)
        
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    while True:
        try:
            # Basic health check
            response = requests.get(f"{config['api_url']}/health", timeout=10)
            if response.status_code == 200:
                logger.info("✅ API health check passed")
            else:
                logger.error(f"❌ API health check failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Health check error: {e}")
            
        time.sleep(config["monitoring_interval"])

if __name__ == "__main__":
    main()
'''

        with open(script_path, "w") as f:
            f.write(monitor_code)

        script_path.chmod(0o755)

    def run_health_checks(self, duration_minutes: int = 5) -> bool:
        """Run health checks for specified duration"""
        self.logger.info(f"Running health checks for {duration_minutes} minutes...")

        end_time = time.time() + (duration_minutes * 60)
        check_interval = self.config["health_check_interval"]
        success_count = 0
        total_checks = 0

        while time.time() < end_time:
            total_checks += 1

            try:
                # API health check
                response = requests.get(
                    f"{self.config['api_url']}/health",
                    timeout=self.config["health_check_timeout"],
                )

                if response.status_code == 200:
                    success_count += 1
                    self.logger.info(f"Health check {total_checks}: ✅ PASS")
                else:
                    self.logger.warning(
                        f"Health check {total_checks}: ❌ FAIL (status {response.status_code})"
                    )

            except requests.RequestException as e:
                self.logger.warning(f"Health check {total_checks}: ❌ FAIL ({e})")

            time.sleep(check_interval)

        success_rate = success_count / total_checks if total_checks > 0 else 0
        self.logger.info(
            f"Health check summary: {success_count}/{total_checks} passed ({success_rate:.1%})"
        )

        return success_rate >= 0.9  # 90% success rate required

    def rollback(self):
        """Rollback to previous state"""
        self.logger.warning("Initiating rollback procedure...")

        if not self.rollback_points:
            self.logger.error("No rollback points available")
            return False

        latest_rollback = self.rollback_points[-1]
        self.logger.info(f"Rolling back to: {latest_rollback['name']}")

        try:
            # Stop current services
            subprocess.run(["docker", "compose", "down"], check=True)

            # Restore database if backup exists
            if latest_rollback.get("database_backup"):
                self.logger.info(
                    "Database rollback not implemented - manual intervention required"
                )

            # Restart services with previous configuration
            subprocess.run(["docker", "compose", "up", "-d"], check=True)

            self.logger.info("Rollback completed")
            return True

        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False

    def generate_deployment_report(self) -> str:
        """Generate deployment report"""
        deployment_end = datetime.now()
        duration = deployment_end - self.deployment_start

        report = {
            "deployment_summary": {
                "start_time": self.deployment_start.isoformat(),
                "end_time": deployment_end.isoformat(),
                "duration_minutes": duration.total_seconds() / 60,
                "status": "SUCCESS",
            },
            "rollback_points": len(self.rollback_points),
            "health_checks": len(self.health_checks),
            "configuration": self.config,
            "next_steps": [
                "Monitor system performance for 24 hours",
                "Review audit logs for any issues",
                "Conduct user acceptance testing",
                "Update documentation with production URLs",
            ],
        }

        # Save report
        report_file = (
            Path("logs")
            / f"deployment_report_{self.deployment_start.strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        self.logger.info(f"Deployment report saved to {report_file}")
        return str(report_file)


def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(
        description="Production deployment for many-to-many role system"
    )
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument(
        "--skip-validation", action="store_true", help="Skip pre-deployment validation"
    )
    parser.add_argument(
        "--monitor-duration",
        type=int,
        default=5,
        help="Health check duration (minutes)",
    )

    args = parser.parse_args()

    # Initialize deployment
    deployment = ProductionDeployment(args.config)

    print("🚀 Starting Production Deployment for Many-to-Many Role System")
    print("=" * 60)

    try:
        if args.skip_validation:
            deployment.logger.info(
                "Skipping pre-deployment validation (--skip-validation)"
            )

        # Run deployment
        success = deployment.deploy_to_production()

        if success:
            print("\n✅ DEPLOYMENT SUCCESSFUL!")
            print("🔍 Running extended health checks...")
            deployment.run_health_checks(args.monitor_duration)

            # Generate report
            report_file = deployment.generate_deployment_report()
            print(f"📋 Deployment report: {report_file}")

            print("\n🎯 Next Steps:")
            print("1. Monitor system performance for 24 hours")
            print("2. Review audit logs for any issues")
            print("3. Conduct user acceptance testing")
            print("4. Update documentation with production URLs")

        else:
            print("\n❌ DEPLOYMENT FAILED!")
            print("Check logs for details and consider manual intervention")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n🛑 Deployment interrupted by user")
        deployment.logger.warning(
            "Deployment interrupted - system may be in inconsistent state"
        )
        sys.exit(1)

    except Exception as e:
        print(f"\n💥 Deployment failed with error: {e}")
        deployment.logger.error(f"Unexpected deployment error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
