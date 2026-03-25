from __future__ import annotations

import os


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
    app_log_level: str = os.getenv("APP_LOG_LEVEL", "INFO").upper()


settings = Settings()
