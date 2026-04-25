from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _to_list(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return default
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or default


class Settings:
    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_service_role_key: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    supabase_schema: str = os.getenv("SUPABASE_SCHEMA", "pricing")
    scn_table: str = os.getenv("SUPABASE_SCN_TABLE", "scn_pricing")
    scn_batch_size: int = _to_int(os.getenv("SCN_BATCH_SIZE"), 500)
    scn_search_max_rows: int = _to_int(os.getenv("SCN_SEARCH_MAX_ROWS"), 200)
    connector_prices_table: str = os.getenv("SUPABASE_CONNECTOR_PRICES_TABLE", "connector_prices")
    connector_max_concurrency: int = max(1, _to_int(os.getenv("CONNECTOR_MAX_CONCURRENCY"), 2))
    app_log_level: str = os.getenv("APP_LOG_LEVEL", "DEBUG").upper()
    cors_allowed_origins: list[str] = _to_list(
        os.getenv("CORS_ALLOWED_ORIGINS"),
        [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://probuy-frontend.onrender.com",
        ],
    )
    cors_allow_origin_regex: str | None = os.getenv(
        "CORS_ALLOW_ORIGIN_REGEX",
        r"^http://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.onrender\.com$|^https://.*\.vercel\.app$",
    )


settings = Settings()
