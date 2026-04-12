from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


ALLOWED_PAGE_KEYS = frozenset({"about", "articles", "artworks", "home", "podcasts", "projects"})
ALLOWED_LANGS = frozenset({"en", "zh"})


@dataclass(frozen=True)
class Settings:
    counters_table_name: str
    uniques_table_name: str
    visitor_hmac_secret: str
    admin_group_name: str
    uniques_ttl_days: int


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    ttl_raw = os.getenv("ANALYTICS_UNIQUES_TTL_DAYS", "7").strip()
    try:
        ttl_days = max(1, int(ttl_raw))
    except ValueError as exc:
        raise RuntimeError("ANALYTICS_UNIQUES_TTL_DAYS must be an integer") from exc

    return Settings(
        counters_table_name=_required_env("ANALYTICS_COUNTERS_TABLE_NAME"),
        uniques_table_name=_required_env("ANALYTICS_UNIQUES_TABLE_NAME"),
        visitor_hmac_secret=_required_env("ANALYTICS_VISITOR_HMAC_SECRET"),
        admin_group_name=_required_env("ANALYTICS_ADMIN_GROUP_NAME"),
        uniques_ttl_days=ttl_days,
    )

