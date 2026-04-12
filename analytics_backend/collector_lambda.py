from __future__ import annotations

from analytics_backend.collector import DynamoCollectorStore, handle_collect_request
from analytics_backend.config import get_settings


_SETTINGS = get_settings()
_STORE = DynamoCollectorStore(
    counters_table_name=_SETTINGS.counters_table_name,
    uniques_table_name=_SETTINGS.uniques_table_name,
)


def handler(event: dict, context: object) -> dict:
    del context
    return handle_collect_request(event, settings=_SETTINGS, store=_STORE)

