"""Backward-compatible model exports.

Prefer importing from app.models.normalized_result.
"""

from app.models.normalized_result import NormalizedResult, SearchAnalysis, SearchResponse

SearchResult = NormalizedResult
