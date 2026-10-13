import os
from pydantic import BaseModel, Field

class Settings(BaseModel):
    APP_NAME: str = "CS2 FACEIT Baiting Analyzer"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'var', 'app.db'))}"
        )
    )

    # Auth & Sessions
    SESSION_COOKIE_NAME: str = "session_id"
    SESSION_MAX_AGE_SECONDS: int = 7 * 24 * 3600  # 7 days
    SESSION_COOKIE_SECURE: bool = Field(
        default_factory=lambda: os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    )
    SESSION_COOKIE_SAMESITE: str = "lax"

    # CORS & CSRF
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Scratch & Quotas
    SCRATCH_DIR: str = Field(
        default_factory=lambda: os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "var", "scratch_demos"))
    )
    UPLOAD_MAX_BYTES: int = 350 * 1024 * 1024       # 350 MB
    DECOMPRESSED_MAX_BYTES: int = int(1.2 * 1024 * 1024 * 1024)  # 1.2 GB
    DISK_MIN_FREE_BYTES: int = 5 * 1024 * 1024 * 1024            # 5 GB
    SCRATCH_MAX_DIR_BYTES: int = 10 * 1024 * 1024 * 1024         # 10 GB
    UPLOAD_TTL_SECONDS: int = 3600                               # 1 hour

    # Rate Limiting & Quotas
    FORWARDED_ALLOW_IPS: list[str] = ["127.0.0.1", "testclient"]
    UPLOAD_RATE_LIMIT: str = "5/minute"
    CONCURRENT_UPLOAD_LIMIT: int = 1
    DAILY_ANALYSIS_QUOTA: int = 10

settings = Settings()
