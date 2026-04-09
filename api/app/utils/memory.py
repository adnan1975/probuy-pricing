from __future__ import annotations

import psutil


def get_rss_mb() -> float:
    """Return resident set size (RSS) in megabytes."""
    usage_mb = psutil.Process().memory_info().rss / (1024 * 1024)
    return usage_mb

