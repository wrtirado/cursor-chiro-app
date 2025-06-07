#!/usr/bin/env python3
"""
Production Monitoring Script for Many-to-Many Role System
Continuous monitoring with alerting and performance tracking
Task 34.12: Production Deployment and Post-Deployment Monitoring
"""

import os
import sys
import time
import json
import logging
import argparse
import requests
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

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
    print("Monitoring will continue with limited functionality")


class ProductionMonitor:
    """Production monitoring system for role-based healthcare application"""

    def __init__(self, config_file: str):
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.metrics = {
            "api_checks": [],
            "role_checks": [],
            "database_checks": [],
            "errors": [],
            "alerts_sent": [],
        }
        self.start_time = datetime.now()

    def setup_logging(self):
        """Setup monitoring logging"""
        log_dir = Path("logs/monitoring")
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = log_dir / f"production_monitor_{timestamp}.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self, config_file: str) -> Dict[str, Any]:
        """Load monitoring configuration"""
        try:
            with open(config_file, "r") as f:
                config = json.load(f)

            # Set defaults for missing values
            defaults = {
                "api_url": "http://localhost:8000",
                "monitoring_interval": 30,
                "health_check_timeout": 10,
                "alert_thresholds": {
                    "api_response_time": 5.0,
                    "error_rate": 0.05,
                    "role_check_time": 1.0,
                    "consecutive_failures": 3,
                },
                "alerting": {
                    "enabled": False,
                    "email": {
                        "smtp_server": "localhost",
                        "smtp_port": 587,
                        "sender": "monitor@healthcare-app.com",
                        "recipients": ["admin@healthcare-app.com"],
                    },
                    "webhook": {"url": "", "enabled": False},
                },
                "database_monitoring": True,
                "performance_monitoring": True,
            }

            for key, value in defaults.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if sub_key not in config[key]:
                            config[key][sub_key] = sub_value

            return config

        except Exception as e:
            print(f"Error loading config file {config_file}: {e}")
            sys.exit(1)

    def run_monitoring(self):
        """Main monitoring loop"""
        self.logger.info("Starting production monitoring...")
        self.logger.info(f"Monitoring URL: {self.config['api_url']}")
        self.logger.info(f"Check interval: {self.config['monitoring_interval']}s")

        consecutive_failures = 0

        try:
            while True:
                check_start = time.time()

                # Run all monitoring checks
                checks_passed = self.run_all_checks()

                if checks_passed:
                    consecutive_failures = 0
                    self.logger.info("✅ All monitoring checks passed")
                else:
                    consecutive_failures += 1
                    self.logger.warning(
                        f"❌ Some checks failed (consecutive failures: {consecutive_failures})"
                    )

                    # Send alert if threshold reached
                    if (
                        consecutive_failures
                        >= self.config["alert_thresholds"]["consecutive_failures"]
                    ):
                        self.send_alert(
                            "Consecutive Monitoring Failures",
                            f"System has failed {consecutive_failures} consecutive health checks",
                        )
                        consecutive_failures = 0  # Reset after sending alert

                # Generate periodic reports
                if self.should_generate_report():
                    self.generate_monitoring_report()

                # Wait for next check
                check_duration = time.time() - check_start
                sleep_time = max(0, self.config["monitoring_interval"] - check_duration)

                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.info("Monitoring stopped by user")
            self.generate_final_report()

        except Exception as e:
            self.logger.error(f"Monitoring failed with error: {e}")
            self.send_alert(
                "Monitoring System Error",
                f"Monitoring system encountered an error: {e}",
            )

    def run_all_checks(self) -> bool:
        """Run all monitoring checks"""
        checks = [
            ("API Health", self.check_api_health),
            ("Database", self.check_database_health),
            ("Role System", self.check_role_system_health),
            ("Authentication", self.check_authentication_health),
            ("Audit Logging", self.check_audit_logging_health),
        ]

        all_passed = True
        check_results = {}

        for check_name, check_func in checks:
            try:
                start_time = time.time()
                result = check_func()
                duration = time.time() - start_time

                check_results[check_name] = {
                    "passed": result,
                    "duration": duration,
                    "timestamp": datetime.now().isoformat(),
                }

                if result:
                    self.logger.debug(f"✅ {check_name} check passed ({duration:.3f}s)")
                else:
                    self.logger.warning(
                        f"❌ {check_name} check failed ({duration:.3f}s)"
                    )
                    all_passed = False

            except Exception as e:
                self.logger.error(f"❌ {check_name} check error: {e}")
                check_results[check_name] = {
                    "passed": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
                all_passed = False

        # Store results for reporting
        self.metrics["checks"] = check_results

        return all_passed

    def check_api_health(self) -> bool:
        """Check API endpoint health"""
        try:
            endpoints = ["/health", "/docs", "/api/v1/auth/status"]

            for endpoint in endpoints:
                url = f"{self.config['api_url']}{endpoint}"
                start_time = time.time()

                response = requests.get(
                    url, timeout=self.config["health_check_timeout"]
                )
                response_time = time.time() - start_time

                self.metrics["api_checks"].append(
                    {
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "response_time": response_time,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # Check response time threshold
                if response_time > self.config["alert_thresholds"]["api_response_time"]:
                    self.logger.warning(
                        f"Slow response from {endpoint}: {response_time:.3f}s"
                    )

                if response.status_code != 200:
                    self.logger.error(
                        f"Bad response from {endpoint}: {response.status_code}"
                    )
                    return False

            return True

        except requests.RequestException as e:
            self.logger.error(f"API health check failed: {e}")
            return False

    def check_database_health(self) -> bool:
        """Check database connectivity and performance"""
        if not self.config.get("database_monitoring", True):
            return True

        try:
            db = SessionLocal()
            start_time = time.time()

            # Basic connectivity test
            result = db.execute(text("SELECT 1"))
            connectivity_time = time.time() - start_time

            # Check table existence
            tables = ["users", "roles", "user_roles", "audit_logs"]
            for table in tables:
                start_time = time.time()
                count_result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = count_result.scalar()
                query_time = time.time() - start_time

                self.metrics["database_checks"].append(
                    {
                        "table": table,
                        "count": count,
                        "query_time": query_time,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            self.logger.debug(f"Database connectivity: {connectivity_time:.3f}s")

            db.close()
            return True

        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False

    def check_role_system_health(self) -> bool:
        """Check role system functionality and performance"""
        try:
            db = SessionLocal()
            start_time = time.time()

            # Check role assignments
            active_assignments = (
                db.query(UserRole).filter(UserRole.is_active == True).count()
            )

            # Test role lookup performance
            test_users = db.query(User).limit(5).all()

            role_check_times = []
            for user in test_users:
                role_start = time.time()
                roles = user.get_active_roles(db)
                role_time = time.time() - role_start
                role_check_times.append(role_time)

            avg_role_time = (
                sum(role_check_times) / len(role_check_times) if role_check_times else 0
            )

            self.metrics["role_checks"].append(
                {
                    "active_assignments": active_assignments,
                    "avg_role_check_time": avg_role_time,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Check performance threshold
            if avg_role_time > self.config["alert_thresholds"]["role_check_time"]:
                self.logger.warning(f"Slow role checking: {avg_role_time:.3f}s average")

            self.logger.debug(
                f"Role system check: {active_assignments} assignments, {avg_role_time:.3f}s avg"
            )

            db.close()
            return True

        except Exception as e:
            self.logger.error(f"Role system health check failed: {e}")
            return False

    def check_authentication_health(self) -> bool:
        """Check authentication system"""
        try:
            auth_url = f"{self.config['api_url']}/api/v1/auth/status"
            response = requests.get(
                auth_url, timeout=self.config["health_check_timeout"]
            )

            if response.status_code == 200:
                self.logger.debug("Authentication system healthy")
                return True
            else:
                self.logger.error(
                    f"Authentication check failed: {response.status_code}"
                )
                return False

        except requests.RequestException as e:
            self.logger.error(f"Authentication health check failed: {e}")
            return False

    def check_audit_logging_health(self) -> bool:
        """Check audit logging system"""
        try:
            db = SessionLocal()

            # Check recent audit logs
            recent_threshold = datetime.now() - timedelta(hours=1)
            recent_logs = (
                db.query(AuditLog)
                .filter(AuditLog.timestamp >= recent_threshold)
                .count()
            )

            # Check for role-related logs
            role_logs = (
                db.query(AuditLog).filter(AuditLog.action.like("%ROLE%")).count()
            )

            self.logger.debug(
                f"Audit logging: {recent_logs} recent logs, {role_logs} role logs"
            )

            db.close()
            return True

        except Exception as e:
            self.logger.error(f"Audit logging health check failed: {e}")
            return False

    def should_generate_report(self) -> bool:
        """Check if it's time to generate a monitoring report"""
        # Generate reports every hour
        uptime = datetime.now() - self.start_time
        return uptime.total_seconds() % 3600 < self.config["monitoring_interval"]

    def generate_monitoring_report(self):
        """Generate monitoring status report"""
        uptime = datetime.now() - self.start_time

        report = {
            "timestamp": datetime.now().isoformat(),
            "uptime_hours": uptime.total_seconds() / 3600,
            "monitoring_config": self.config["api_url"],
            "recent_metrics": {
                "api_checks": len(self.metrics.get("api_checks", [])),
                "role_checks": len(self.metrics.get("role_checks", [])),
                "database_checks": len(self.metrics.get("database_checks", [])),
                "errors": len(self.metrics.get("errors", [])),
                "alerts_sent": len(self.metrics.get("alerts_sent", [])),
            },
        }

        # Calculate performance statistics
        if self.metrics.get("api_checks"):
            recent_api_checks = self.metrics["api_checks"][-10:]  # Last 10 checks
            avg_response_time = sum(
                check["response_time"] for check in recent_api_checks
            ) / len(recent_api_checks)
            report["performance"] = {
                "avg_api_response_time": avg_response_time,
                "api_success_rate": sum(
                    1 for check in recent_api_checks if check["status_code"] == 200
                )
                / len(recent_api_checks),
            }

        if self.metrics.get("role_checks"):
            recent_role_checks = self.metrics["role_checks"][-5:]  # Last 5 checks
            avg_role_time = sum(
                check["avg_role_check_time"] for check in recent_role_checks
            ) / len(recent_role_checks)
            report["performance"]["avg_role_check_time"] = avg_role_time

        # Save report
        report_dir = Path("logs/monitoring/reports")
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        report_file = report_dir / f"monitoring_report_{timestamp}.json"

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        self.logger.info(f"Monitoring report generated: {report_file}")

    def generate_final_report(self):
        """Generate final monitoring report when stopping"""
        uptime = datetime.now() - self.start_time

        final_report = {
            "monitoring_session": {
                "start_time": self.start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "total_uptime_hours": uptime.total_seconds() / 3600,
            },
            "total_metrics": {
                "api_checks_performed": len(self.metrics.get("api_checks", [])),
                "role_checks_performed": len(self.metrics.get("role_checks", [])),
                "database_checks_performed": len(
                    self.metrics.get("database_checks", [])
                ),
                "total_errors": len(self.metrics.get("errors", [])),
                "alerts_sent": len(self.metrics.get("alerts_sent", [])),
            },
            "performance_summary": self.calculate_performance_summary(),
        }

        # Save final report
        report_dir = Path("logs/monitoring")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_report_file = report_dir / f"final_monitoring_report_{timestamp}.json"

        with open(final_report_file, "w") as f:
            json.dump(final_report, f, indent=2)

        self.logger.info(f"Final monitoring report saved: {final_report_file}")

    def calculate_performance_summary(self) -> Dict[str, Any]:
        """Calculate performance statistics summary"""
        summary = {}

        if self.metrics.get("api_checks"):
            api_checks = self.metrics["api_checks"]
            response_times = [check["response_time"] for check in api_checks]
            success_count = sum(
                1 for check in api_checks if check["status_code"] == 200
            )

            summary["api_performance"] = {
                "avg_response_time": sum(response_times) / len(response_times),
                "max_response_time": max(response_times),
                "min_response_time": min(response_times),
                "success_rate": success_count / len(api_checks),
                "total_requests": len(api_checks),
            }

        if self.metrics.get("role_checks"):
            role_checks = self.metrics["role_checks"]
            role_times = [check["avg_role_check_time"] for check in role_checks]

            summary["role_performance"] = {
                "avg_role_check_time": sum(role_times) / len(role_times),
                "max_role_check_time": max(role_times),
                "min_role_check_time": min(role_times),
                "total_role_checks": len(role_checks),
            }

        return summary

    def send_alert(self, subject: str, message: str):
        """Send alert notification"""
        if not self.config["alerting"]["enabled"]:
            self.logger.warning(f"Alert would be sent: {subject} - {message}")
            return

        alert_info = {
            "subject": subject,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }

        self.metrics["alerts_sent"].append(alert_info)

        try:
            # Send email alert
            if self.config["alerting"]["email"]["enabled"]:
                self.send_email_alert(subject, message)

            # Send webhook alert
            if self.config["alerting"]["webhook"]["enabled"]:
                self.send_webhook_alert(subject, message)

            self.logger.warning(f"Alert sent: {subject}")

        except Exception as e:
            self.logger.error(f"Failed to send alert: {e}")

    def send_email_alert(self, subject: str, message: str):
        """Send email alert"""
        email_config = self.config["alerting"]["email"]

        msg = MimeMultipart()
        msg["From"] = email_config["sender"]
        msg["To"] = ", ".join(email_config["recipients"])
        msg["Subject"] = f"[HEALTHCARE APP ALERT] {subject}"

        body = f"""
Production Monitoring Alert

Subject: {subject}
Time: {datetime.now().isoformat()}
System: {self.config['api_url']}

Details:
{message}

This is an automated alert from the healthcare application monitoring system.
"""

        msg.attach(MimeText(body, "plain"))

        server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
        server.starttls()
        # Note: Add authentication if needed
        # server.login(username, password)
        text = msg.as_string()
        server.sendmail(email_config["sender"], email_config["recipients"], text)
        server.quit()

    def send_webhook_alert(self, subject: str, message: str):
        """Send webhook alert"""
        webhook_config = self.config["alerting"]["webhook"]

        payload = {
            "subject": subject,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "system": self.config["api_url"],
            "level": "warning",
        }

        requests.post(webhook_config["url"], json=payload, timeout=10)


def main():
    """Main monitoring function"""
    parser = argparse.ArgumentParser(
        description="Production monitoring for many-to-many role system"
    )
    parser.add_argument("--config", required=True, help="Monitoring configuration file")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()

    # Validate config file exists
    if not os.path.exists(args.config):
        print(f"Configuration file not found: {args.config}")
        sys.exit(1)

    print("🔍 Starting Production Monitoring for Healthcare Application")
    print("=" * 60)

    try:
        # Initialize and start monitoring
        monitor = ProductionMonitor(args.config)
        monitor.run_monitoring()

    except Exception as e:
        print(f"💥 Monitoring failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
