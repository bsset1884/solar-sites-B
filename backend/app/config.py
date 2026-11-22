"""Settings, read from environment variables so the same image runs everywhere."""

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path  # where the SQLite database file lives
    static_dir: Path  # the built React app, served on "/"
    pvgis_base_url: str
    pvgis_timeout_seconds: float
    session_ttl_seconds: int
    cookie_secure: bool  # force the Secure cookie flag (it is set anyway on HTTPS)
    login_max_failures: int  # failed logins per email within the window before 429
    login_window_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.getenv("DATA_DIR", BACKEND_DIR / "data")),
            static_dir=Path(os.getenv("STATIC_DIR", BACKEND_DIR / "static")),
            pvgis_base_url=os.getenv("PVGIS_BASE_URL", "https://re.jrc.ec.europa.eu/api/v5_3"),
            pvgis_timeout_seconds=float(os.getenv("PVGIS_TIMEOUT_SECONDS", "30")),
            session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", str(7 * 24 * 3600))),
            cookie_secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
            login_max_failures=int(os.getenv("LOGIN_MAX_FAILURES", "10")),
            login_window_seconds=int(os.getenv("LOGIN_WINDOW_SECONDS", str(15 * 60))),
        )
