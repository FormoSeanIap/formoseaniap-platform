from __future__ import annotations

from analytics_backend.admin import DynamoAnalyticsReader, handle_admin_request
from analytics_backend.config import get_settings


_SETTINGS = get_settings()
_READER = DynamoAnalyticsReader(counters_table_name=_SETTINGS.counters_table_name)


def handler(event: dict, context: object) -> dict:
    del context
    return handle_admin_request(event, settings=_SETTINGS, reader=_READER)
