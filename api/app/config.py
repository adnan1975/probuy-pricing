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


settings = Settings()
