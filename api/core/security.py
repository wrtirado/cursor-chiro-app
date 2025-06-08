from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
import re
import hashlib
from api.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# HIPAA-compliant password policy constants
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True
REQUIRE_DIGITS = True
REQUIRE_SPECIAL_CHARS = True
SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
PASSWORD_HISTORY_COUNT = 12  # Remember last 12 passwords
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


class PasswordValidationResult:
    """Result object for password validation"""

    def __init__(self, is_valid: bool, errors: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []


def validate_password_complexity(password: str) -> PasswordValidationResult:
    """
    Validate password meets HIPAA-compliant complexity requirements.

    HIPAA Security Rule requirements:
    - Minimum 12 characters (stronger than minimum 8)
    - Mix of uppercase, lowercase, numbers, special characters
    - No common patterns or dictionary words
    """
    errors = []

    # Length validation
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"Password must not exceed {MAX_PASSWORD_LENGTH} characters")

    # Character type requirements
    if REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")

    if REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")

    if REQUIRE_DIGITS and not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")

    if REQUIRE_SPECIAL_CHARS and not re.search(
        f"[{re.escape(SPECIAL_CHARS)}]", password
    ):
        errors.append(
            f"Password must contain at least one special character: {SPECIAL_CHARS}"
        )

    # Common pattern checks
    if re.search(r"(.)\1{2,}", password):  # 3+ repeated characters
        errors.append("Password must not contain 3 or more repeated characters")

    if re.search(
        r"(012|123|234|345|456|567|678|789|890|abc|bcd|cde)", password.lower()
    ):
        errors.append("Password must not contain sequential characters")

    # Common weak patterns
    weak_patterns = [
        r"password",
        r"admin",
        r"user",
        r"login",
        r"welcome",
        r"qwerty",
        r"abc123",
        r"123456",
        r"letmein",
    ]
    for pattern in weak_patterns:
        if re.search(pattern, password.lower()):
            errors.append("Password must not contain common words or patterns")
            break

    return PasswordValidationResult(len(errors) == 0, errors)


def calculate_password_strength(password: str) -> Dict[str, any]:
    """
    Calculate password strength score and provide feedback.
    Returns score 0-100 and strength category.
    """
    score = 0
    feedback = []

    # Length scoring (up to 25 points)
    length_score = min(25, len(password) * 2)
    score += length_score

    # Character variety (up to 40 points, 10 each)
    if re.search(r"[a-z]", password):
        score += 10
    else:
        feedback.append("Add lowercase letters")

    if re.search(r"[A-Z]", password):
        score += 10
    else:
        feedback.append("Add uppercase letters")

    if re.search(r"\d", password):
        score += 10
    else:
        feedback.append("Add numbers")

    if re.search(f"[{re.escape(SPECIAL_CHARS)}]", password):
        score += 10
    else:
        feedback.append("Add special characters")

    # Complexity bonus (up to 35 points)
    unique_chars = len(set(password))
    complexity_score = min(15, unique_chars)
    score += complexity_score

    # No repeated patterns bonus
    if not re.search(r"(.)\1{2,}", password):
        score += 10
    else:
        feedback.append("Avoid repeated characters")

    # No sequential patterns bonus
    if not re.search(
        r"(012|123|234|345|456|567|678|789|890|abc|bcd|cde)", password.lower()
    ):
        score += 10
    else:
        feedback.append("Avoid sequential patterns")

    # Determine strength category
    if score >= 90:
        strength = "Excellent"
    elif score >= 75:
        strength = "Strong"
    elif score >= 60:
        strength = "Good"
    elif score >= 40:
        strength = "Weak"
    else:
        strength = "Very Weak"

    return {
        "score": score,
        "strength": strength,
        "feedback": feedback,
        "is_strong": score >= 75,
    }


def hash_password_for_history(password: str) -> str:
    """Create a hash for password history comparison (different from login hash)"""
    return hashlib.sha256(password.encode()).hexdigest()


def check_password_history(password: str, password_history: List[str]) -> bool:
    """
    Check if password was used recently.
    Returns True if password is in history (should be rejected).
    """
    if not password_history:
        return False

    password_hash = hash_password_for_history(password)
    return password_hash in password_history


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def is_account_locked(failed_attempts: int, last_attempt: Optional[datetime]) -> bool:
    """Check if account should be locked due to failed login attempts"""
    if failed_attempts < MAX_LOGIN_ATTEMPTS:
        return False

    if not last_attempt:
        return True

    lockout_expires = last_attempt + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    return datetime.utcnow() < lockout_expires


def get_lockout_remaining_time(last_attempt: datetime) -> int:
    """Get remaining lockout time in minutes"""
    if not last_attempt:
        return 0

    lockout_expires = last_attempt + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    remaining = lockout_expires - datetime.utcnow()

    if remaining.total_seconds() <= 0:
        return 0

    return int(remaining.total_seconds() / 60) + 1
