from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from analytics_backend.collector import ValidationError, decode_cursor_offset, encode_cursor_offset
from analytics_backend.config import ALLOWED_DOMAINS, Settings
from analytics_backend.http import json_response


MAX_RANGE_DAYS = 365
ALLOWED_GROUP_MODES = {"combined", "variant"}


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    @property
    def day_count(self) -> int:
        return (self.end - self.start).days + 1

    def days(self) -> list[date]:
        return [self.start + timedelta(days=index) for index in range(self.day_count)]


def parse_iso_date(value: str | None, *, field_name: str) -> date:
    if not value:
        raise ValidationError(f"{field_name} is required.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be in YYYY-MM-DD format.") from exc


def parse_date_range(params: dict[str, Any] | None) -> DateRange:
    params = params or {}
    start = parse_iso_date(params.get("from"), field_name="from")
    end = parse_iso_date(params.get("to"), field_name="to")
    if end < start:
        raise ValidationError("to must be on or after from.")
    day_count = (end - start).days + 1
    if day_count > MAX_RANGE_DAYS:
        raise ValidationError(f"Date range must be {MAX_RANGE_DAYS} days or fewer.")
    return DateRange(start=start, end=end)


def parse_limit(raw_limit: str | None) -> int:
    if not raw_limit:
        return 50
    try:
        value = int(raw_limit)
    except ValueError as exc:
        raise ValidationError("limit must be an integer.") from exc
    return min(max(value, 1), 100)


def parse_domain_filter(raw_domain: str | None) -> str | None:
    if not raw_domain:
        return None
    if raw_domain not in ALLOWED_DOMAINS:
        raise ValidationError("domain must be 'main', 'engineering', or omitted.")
    return raw_domain


def _get_item_domain(item: dict[str, Any]) -> str:
    """Return the domain for an item, defaulting to 'main' for old-format items."""
    return str(item.get("domain") or "main")


def _matches_domain_filter(item: dict[str, Any], domain_filter: str | None) -> bool:
    """Check if an item matches the given domain filter. Always True when no filter."""
    if domain_filter is None:
        return True
    return _get_item_domain(item) == domain_filter


def parse_groups_claim(claims: dict[str, Any]) -> list[str]:
    raw = claims.get("cognito:groups")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]

    value = str(raw).strip()
    if not value:
        return []

    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip('"').strip("'") for part in inner.split(",") if part.strip()]

    if "," in value:
        return [part.strip() for part in value.split(",") if part.strip()]

    return [value]


def require_admin_group(claims: dict[str, Any], *, expected_group: str) -> None:
    groups = parse_groups_claim(claims)
    if expected_group not in groups:
        raise PermissionError("Authenticated user is not in the analytics admin group.")


class DynamoAnalyticsReader:
    def __init__(self, *, counters_table_name: str, dynamodb_resource: Any | None = None) -> None:
        self._resource = dynamodb_resource or boto3.resource("dynamodb")
        self.counters_table = self._resource.Table(counters_table_name)

    def query_day(self, day_value: date) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        response = self.counters_table.query(
            IndexName="gsi1",
            KeyConditionExpression=Key("gsi1pk").eq(f"DAY#{day_value.isoformat()}"),
        )
        items.extend(response.get("Items", []))

        while "LastEvaluatedKey" in response:
            response = self.counters_table.query(
                IndexName="gsi1",
                KeyConditionExpression=Key("gsi1pk").eq(f"DAY#{day_value.isoformat()}"),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        return items

    def query_entity_range(self, entity_key: str, date_range: DateRange) -> list[dict[str, Any]]:
        response = self.counters_table.query(
            KeyConditionExpression=Key("pk").eq(entity_key) & Key("sk").between(
                f"DAY#{date_range.start.isoformat()}",
                f"DAY#{date_range.end.isoformat()}",
            ),
        )
        items = list(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = self.counters_table.query(
                KeyConditionExpression=Key("pk").eq(entity_key) & Key("sk").between(
                    f"DAY#{date_range.start.isoformat()}",
                    f"DAY#{date_range.end.isoformat()}",
                ),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return items


def _item_views(item: dict[str, Any]) -> int:
    return int(item.get("views") or 0)


def _item_unique_visitors(item: dict[str, Any]) -> int:
    return int(item.get("unique_visitors") or 0)


def build_overview_payload(
    reader: DynamoAnalyticsReader,
    date_range: DateRange,
    *,
    domain_filter: str | None = None,
) -> dict[str, Any]:
    daily_rows = []
    totals = {
        "site_views": 0,
        "site_unique_visitors": 0,
        "article_views": 0,
        "article_unique_visitors": 0,
    }

    for current_day in date_range.days():
        items = reader.query_day(current_day)

        if domain_filter is not None:
            # When filtering by domain, use the per-domain SITE#ALL#<domain> key
            site_pk = f"SITE#ALL#{domain_filter}"
            site_item = next((item for item in items if item.get("pk") == site_pk), None)
            article_items = [
                item for item in items
                if item.get("entity_type") == "article" and _matches_domain_filter(item, domain_filter)
            ]
        else:
            # Combined: use the aggregate SITE#ALL key
            site_item = next((item for item in items if item.get("pk") == "SITE#ALL"), None)
            article_items = [item for item in items if item.get("entity_type") == "article"]

        row = {
            "date": current_day.isoformat(),
            "site_views": _item_views(site_item or {}),
            "site_unique_visitors": _item_unique_visitors(site_item or {}),
            "article_views": sum(_item_views(item) for item in article_items),
            "article_unique_visitors": sum(_item_unique_visitors(item) for item in article_items),
        }
        daily_rows.append(row)

        for key in totals:
            totals[key] += row[key]

    result: dict[str, Any] = {
        "from": date_range.start.isoformat(),
        "to": date_range.end.isoformat(),
        "summary": totals,
        "daily": daily_rows,
    }
    if domain_filter is not None:
        result["domain"] = domain_filter
    return result


def build_articles_payload(
    reader: DynamoAnalyticsReader,
    date_range: DateRange,
    *,
    group_mode: str,
    limit: int,
    cursor: str | None,
    domain_filter: str | None = None,
) -> dict[str, Any]:
    if group_mode not in ALLOWED_GROUP_MODES:
        raise ValidationError("group must be 'combined' or 'variant'.")

    aggregates: dict[str, dict[str, Any]] = {}
    for current_day in date_range.days():
        for item in reader.query_day(current_day):
            if item.get("entity_type") != "article":
                continue
            if not _matches_domain_filter(item, domain_filter):
                continue

            article_id = str(item.get("entity_id") or "")
            lang = item.get("lang")
            aggregate_key = article_id if group_mode == "combined" else f"{article_id}#{lang}"
            current = aggregates.setdefault(
                aggregate_key,
                {
                    "article_id": article_id,
                    "lang": lang if group_mode == "variant" else None,
                    "views": 0,
                    "unique_visitors": 0,
                    "languages": {},
                },
            )
            current["views"] += _item_views(item)
            current["unique_visitors"] += _item_unique_visitors(item)
            if lang:
                language_bucket = current["languages"].setdefault(lang, {"views": 0, "unique_visitors": 0})
                language_bucket["views"] += _item_views(item)
                language_bucket["unique_visitors"] += _item_unique_visitors(item)

    items = sorted(
        aggregates.values(),
        key=lambda item: (-int(item["views"]), -int(item["unique_visitors"]), str(item["article_id"]), str(item["lang"] or "")),
    )

    offset = decode_cursor_offset(cursor)
    page = items[offset : offset + limit]
    next_offset = offset + limit if offset + limit < len(items) else None
    return {
        "from": date_range.start.isoformat(),
        "to": date_range.end.isoformat(),
        "group": group_mode,
        "items": page,
        "next_cursor": encode_cursor_offset(next_offset),
    }


def build_article_detail_payload(
    reader: DynamoAnalyticsReader,
    date_range: DateRange,
    *,
    article_id: str,
    domain_filter: str | None = None,
) -> dict[str, Any]:
    article_id = article_id.strip()
    if not article_id:
        raise ValidationError("article_id is required.")

    # Determine which domain-scoped entity keys to query
    domains_to_query = [domain_filter] if domain_filter else list(ALLOWED_DOMAINS)

    per_language_items: dict[str, list[dict[str, Any]]] = {"en": [], "zh": []}
    for lang in ("en", "zh"):
        for domain in domains_to_query:
            key = f"ARTICLE#{article_id}#{lang}#{domain}"
            per_language_items[lang].extend(reader.query_entity_range(key, date_range))
        # Also query old-format keys (no domain suffix) for backward compatibility
        old_key = f"ARTICLE#{article_id}#{lang}"
        old_items = reader.query_entity_range(old_key, date_range)
        if old_items:
            # Old-format items are treated as "main"
            if domain_filter is None or domain_filter == "main":
                per_language_items[lang].extend(old_items)

    daily = {
        current_day.isoformat(): {
            "date": current_day.isoformat(),
            "combined": {"views": 0, "unique_visitors": 0},
            "by_language": {
                "en": {"views": 0, "unique_visitors": 0},
                "zh": {"views": 0, "unique_visitors": 0},
            },
            "by_domain": {
                "main": {"views": 0, "unique_visitors": 0},
                "engineering": {"views": 0, "unique_visitors": 0},
            },
        }
        for current_day in date_range.days()
    }

    by_language: dict[str, dict[str, Any]] = {
        "en": {"views": 0, "unique_visitors": 0},
        "zh": {"views": 0, "unique_visitors": 0},
    }
    by_domain: dict[str, dict[str, Any]] = {
        "main": {"views": 0, "unique_visitors": 0},
        "engineering": {"views": 0, "unique_visitors": 0},
    }
    combined = {"views": 0, "unique_visitors": 0}

    for lang, items in per_language_items.items():
        for item in items:
            item_date = str(item.get("date") or "") or str(item.get("sk", "")).replace("DAY#", "")
            if item_date not in daily:
                continue

            views = _item_views(item)
            unique_visitors = _item_unique_visitors(item)
            item_domain = _get_item_domain(item)

            by_language[lang]["views"] += views
            by_language[lang]["unique_visitors"] += unique_visitors
            combined["views"] += views
            combined["unique_visitors"] += unique_visitors
            by_domain[item_domain]["views"] += views
            by_domain[item_domain]["unique_visitors"] += unique_visitors

            daily[item_date]["by_language"][lang]["views"] += views
            daily[item_date]["by_language"][lang]["unique_visitors"] += unique_visitors
            daily[item_date]["combined"]["views"] += views
            daily[item_date]["combined"]["unique_visitors"] += unique_visitors
            daily[item_date]["by_domain"][item_domain]["views"] += views
            daily[item_date]["by_domain"][item_domain]["unique_visitors"] += unique_visitors

    result: dict[str, Any] = {
        "article_id": article_id,
        "from": date_range.start.isoformat(),
        "to": date_range.end.isoformat(),
        "combined": combined,
        "by_language": by_language,
        "by_domain": by_domain,
        "daily": list(daily.values()),
    }
    if domain_filter is not None:
        result["domain"] = domain_filter
    return result


def _claims_from_event(event: dict[str, Any]) -> dict[str, Any]:
    return (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )


def _session_payload(claims: dict[str, Any]) -> dict[str, Any]:
    groups = parse_groups_claim(claims)
    return {
        "authorized": True,
        "groups": groups,
        "user": {
            "sub": claims.get("sub"),
            "username": claims.get("cognito:username") or claims.get("username") or claims.get("sub"),
        },
    }


def handle_admin_request(
    event: dict[str, Any],
    *,
    settings: Settings,
    reader: DynamoAnalyticsReader,
) -> dict[str, Any]:
    claims = _claims_from_event(event)
    try:
        require_admin_group(claims, expected_group=settings.admin_group_name)
    except PermissionError as exc:
        return json_response(403, {"error": str(exc)})

    route_key = str(event.get("routeKey") or "")
    params = event.get("queryStringParameters") or {}

    try:
        if route_key == "GET /analytics-api/admin/session":
            return json_response(200, _session_payload(claims))

        domain_filter = parse_domain_filter(params.get("domain"))

        if route_key == "GET /analytics-api/admin/overview":
            date_range = parse_date_range(params)
            return json_response(200, build_overview_payload(reader, date_range, domain_filter=domain_filter))

        if route_key == "GET /analytics-api/admin/articles":
            date_range = parse_date_range(params)
            group_mode = str(params.get("group") or "combined")
            limit = parse_limit(params.get("limit"))
            cursor = params.get("cursor")
            return json_response(
                200,
                build_articles_payload(
                    reader,
                    date_range,
                    group_mode=group_mode,
                    limit=limit,
                    cursor=cursor,
                    domain_filter=domain_filter,
                ),
            )

        if route_key == "GET /analytics-api/admin/articles/{article_id}":
            date_range = parse_date_range(params)
            article_id = (
                event.get("pathParameters", {}) or {}
            ).get("article_id")
            return json_response(
                200,
                build_article_detail_payload(
                    reader, date_range, article_id=str(article_id or ""), domain_filter=domain_filter
                ),
            )
    except ValidationError as exc:
        return json_response(400, {"error": str(exc)})

    return json_response(404, {"error": "Route not found."})
