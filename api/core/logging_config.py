import logging
import logging.handlers
import sys
import json
import os
from pathlib import Path

from api.core.config import settings

# Ensure log directory exists
log_dir = Path(settings.AUDIT_LOG_FILE).parent
log_dir.mkdir(parents=True, exist_ok=True)
app_log_dir = Path(settings.APP_LOG_FILE).parent
app_log_dir.mkdir(parents=True, exist_ok=True)


# JSON Formatter
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger_name": record.name,
            # Add other standard fields if needed
            # "pathname": record.pathname,
            # "lineno": record.lineno,
        }
        # Add extra fields passed to the logger
        if hasattr(record, "props") and isinstance(record.props, dict):
            log_record.update(record.props)

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


# --- Audit Logger Setup ---
def setup_audit_logger():
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(settings.LOG_LEVEL.upper())
    audit_logger.propagate = False  # Prevent audit logs going to root logger/console

    # File handler for audit logs (JSON format)
    # Use RotatingFileHandler for production to manage file size
    audit_handler = logging.handlers.RotatingFileHandler(
        settings.AUDIT_LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,  # 10MB per file, 5 backups
    )
    audit_formatter = JsonFormatter()
    audit_handler.setFormatter(audit_formatter)
    audit_logger.addHandler(audit_handler)
    return audit_logger


# --- General Application Logger Setup ---
def setup_app_logger():
    # Basic configuration for general logs (can be enhanced)
    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.handlers.RotatingFileHandler(
                settings.APP_LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3
            ),
            logging.StreamHandler(sys.stdout),  # Also log to console
        ],
    )
    # Get the root logger or specific app logger if needed
    app_logger = logging.getLogger("app")  # Or just logging.getLogger()
    return app_logger


# Instantiate loggers
audit_log = setup_audit_logger()
app_log = setup_app_logger()  # General logger

# Example usage (will be done via a service usually):
# audit_log.info("User logged in", extra={'props': {'user_id': 1, 'ip_address': '127.0.0.1'}})
# app_log.info("Application starting up")
