from __future__ import annotations

import resource


def get_rss_mb() -> float:
    """Return resident set size (RSS) in megabytes."""
    usage_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return usage_kb / 1024.0

