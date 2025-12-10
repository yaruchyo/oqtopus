import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

IS_PRODUCTION = os.getenv("APP_ENV") == "production"


# 2. Define a helper to handle the logic centrally
def get_env_secure(key, default_dev_value, help_msg=None):
    """
    Retreives env var.
    - If in Prod and missing: Raises ValueError.
    - If in Dev and missing: Returns default_dev_value and logs warning.
    - If present: Returns value.
    """
    value = os.getenv(key)

    if value:
        return value

    if IS_PRODUCTION:
        error_text = f"CRITICAL: {key} must be set in the production environment."
        if help_msg:
            error_text += f" {help_msg}"
        raise ValueError(error_text)
    else:
        logger.warning(
            f"{key} not set - using default dev fallback: '{default_dev_value}'"
        )
        return default_dev_value


class Config(object):
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_VERSION = os.getenv("GEMINI_VERSION")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    PK_STORAGE_TYPE = os.getenv("PK_STORAGE_TYPE", "local").lower()
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

    # --- CLEANER IMPLEMENTATION START ---

    SECRET_KEY = get_env_secure(
        "SECRET_KEY",
        default_dev_value="dev_fallback_constant_secret_key_888",
        help_msg='Generate with: python -c "import secrets; print(secrets.token_hex(32))"',
    )

    SALT_KEY = get_env_secure(
        "PK_ENCRYPTION_SALT",  # Note: User code checked PK_ENCRYPTION_SALT but assigned to SALT_KEY
        default_dev_value="dev_fallback_constant_secret_key_888",
        help_msg='Generate with: python -c "import secrets; print(secrets.token_hex(32))"',
    )

    # --- CLEANER IMPLEMENTATION END ---

    # Rate limiting configuration
    RATELIMIT_DEFAULT = "200 per day, 50 per hour"
    RATELIMIT_STORAGE_URL = "memory://"
    RATELIMIT_STRATEGY = "fixed-window"

    # Session security settings
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    SENDER_EMAIL = os.getenv("SENDER_EMAIL", None)
    SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD", None)
    SMTP_SERVER = os.getenv(
        "SMTP_SERVER", "smtp.gmail.com"
    )  # Default to Gmail's SMTP server
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))  # Default to Gmail's TLS port
    RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", None)


class ProductionConfig(Config):
    DEBUG = False
    MONGO_DB_USER = os.getenv("MONGO_DB_USER")
    MONGO_DB_PASS = os.getenv("MONGO_DB_PASS")
    MONGO_DB_REST_URL = os.getenv("MONGO_DB_REST_URL")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
    SESSION_COOKIE_SECURE = True


class DevelopmentConfig(Config):
    DEBUG = True
    MONGO_DB_USER = os.getenv("MONGO_DB_USER")
    MONGO_DB_PASS = os.getenv("MONGO_DB_PASS")
    MONGO_DB_REST_URL = os.getenv("MONGO_DB_REST_URL")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME_TEST")
