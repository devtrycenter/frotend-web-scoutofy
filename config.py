# ==========================================================
# CONFIG.PY
# ==========================================================

import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ==========================================================
# BASE CONFIG
# ==========================================================

class Config:
    """
    Base Configuration
    """

    # ======================================================
    # FLASK
    # ======================================================
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "change-this-secret-key"
    )

    DEBUG = False
    TESTING = False

    # ======================================================
    # APP
    # ======================================================
    APP_NAME = os.getenv(
        "APP_NAME",
        "Scoutify Frontend"
    )

    APP_VERSION = os.getenv(
        "APP_VERSION",
        "1.0.0"
    )

    APP_URL = os.getenv(
        "APP_URL",
        "http://localhost:5000"
    )

    # ======================================================
    # FASTAPI BACKEND
    # ======================================================
    API_BASE_URL = os.getenv(
        "API_BASE_URL",
        "http://127.0.0.1:5000/api"
    )

    API_TIMEOUT = int(
        os.getenv(
            "API_TIMEOUT",
            30
        )
    )

    # ======================================================
    # SESSION
    # ======================================================
    SESSION_COOKIE_NAME = "scoutify_session"

    SESSION_COOKIE_HTTPONLY = True

    SESSION_COOKIE_SAMESITE = "Lax"

    SESSION_COOKIE_SECURE = (
        os.getenv(
            "SESSION_COOKIE_SECURE",
            "False"
        ).lower()
        == "true"
    )

    PERMANENT_SESSION_LIFETIME = 86400

    # ======================================================
    # SECURITY
    # ======================================================
    REMEMBER_COOKIE_HTTPONLY = True

    REMEMBER_COOKIE_SECURE = (
        os.getenv(
            "REMEMBER_COOKIE_SECURE",
            "False"
        ).lower()
        == "true"
    )

    # ======================================================
    # UPLOAD
    # ======================================================
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        "uploads"
    )

    MAX_CONTENT_LENGTH = (
        10 * 1024 * 1024
    )  # 10 MB

    ALLOWED_IMAGE_EXTENSIONS = {
        "jpg",
        "jpeg",
        "png",
        "webp"
    }

    # ======================================================
    # PAGINATION
    # ======================================================
    DEFAULT_PAGE_SIZE = int(
        os.getenv(
            "DEFAULT_PAGE_SIZE",
            10
        )
    )

    MAX_PAGE_SIZE = int(
        os.getenv(
            "MAX_PAGE_SIZE",
            100
        )
    )

    # ======================================================
    # LOGGING
    # ======================================================
    LOG_LEVEL = os.getenv(
        "LOG_LEVEL",
        "INFO"
    )

    # ======================================================
    # UI
    # ======================================================
    SITE_TITLE = os.getenv(
        "SITE_TITLE",
        "Scoutify"
    )

    SITE_DESCRIPTION = os.getenv(
        "SITE_DESCRIPTION",
        "Scoutify Web Application"
    )

    # ======================================================
    # CUSTOM
    # ======================================================
    COMPANY_NAME = os.getenv(
        "COMPANY_NAME",
        "Scoutify"
    )

    SUPPORT_EMAIL = os.getenv(
        "SUPPORT_EMAIL",
        "support@trycenter.my.id"
    )

# ==========================================================
# DEVELOPMENT
# ==========================================================

class DevelopmentConfig(Config):
    DEBUG = True

# ==========================================================
# PRODUCTION
# ==========================================================

class ProductionConfig(Config):
    DEBUG = False

# ==========================================================
# TESTING
# ==========================================================

class TestingConfig(Config):
    TESTING = True
    DEBUG = True

# ==========================================================
# CONFIG MAPPER
# ==========================================================

config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig
}

# ==========================================================
# GET CONFIG
# ==========================================================

def get_config():
    env = os.getenv(
        "ENV",
        "development"
    ).lower()

    return config_by_name.get(
        env,
        DevelopmentConfig
    )