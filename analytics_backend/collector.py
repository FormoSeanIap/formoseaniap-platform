from __future__ import annotations

import hashlib
import hmac
import json
import re
from base64 import b64decode, urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from analytics_backend.config import ALLOWED_DOMAINS, ALLOWED_LANGS, ALLOWED_PAGE_KEYS, Settings
from analytics_backend.http import json_response


VISITOR_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{7,127}$")


class ValidationError(ValueError):
    """Raised when the collector receives an invalid event payload."""


@dataclass(frozen=True)
class ViewEvent:
    scope: str
    page_key: str | None
    article_id: str | None
    lang: str | None
    visitor_id: str
    domain: str

    @property
    def entity_key(self) -> str:
        if self.scope == "page":
            return f"PAGE#{self.page_key}#{self.domain}"
        return f"ARTICLE#{self.article_id}#{self.lang}#{self.domain}"

    @property
    def entity_type(self) -> str:
        return self.scope

    @property
    def entity_id(self) -> str:
        if self.scope == "page":
            return str(self.page_key)
        return str(self.article_id)


def _coerce_nullable_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_event_body(raw_body: str | None) -> dict[str, Any]:
    if not raw_body:
        raise ValidationError("Request body is required.")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValidationError("Request body must be valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")

    return payload


def validate_view_event(payload: dict[str, Any]) -> ViewEvent:
    scope = _coerce_nullable_string(payload.get("scope"))
    if scope not in {"page", "article"}:
        raise ValidationError("scope must be 'page' or 'article'.")

    visitor_id = _coerce_nullable_string(payload.get("visitor_id"))
    if visitor_id is None or not VISITOR_ID_RE.fullmatch(visitor_id):
        raise ValidationError("visitor_id must be a UUID-like string.")

    domain = _coerce_nullable_string(payload.get("domain"))
    if domain is None:
        raise ValidationError("domain is required.")
    if domain not in ALLOWED_DOMAINS:
        raise ValidationError("domain must be 'main' or 'engineering'.")

    page_key = _coerce_nullable_string(payload.get("page_key"))
    article_id = _coerce_nullable_string(payload.get("article_id"))
    lang = _coerce_nullable_string(payload.get("lang"))

    if scope == "page":
        if page_key not in ALLOWED_PAGE_KEYS:
            raise ValidationError(f"page_key must be one of: {', '.join(sorted(ALLOWED_PAGE_KEYS))}.")
        if article_id is not None or lang is not None:
            raise ValidationError("article_id and lang must be null for page events.")
    else:
        if article_id is None:
            raise ValidationError("article_id is required for article events.")
        if lang not in ALLOWED_LANGS:
            raise ValidationError("lang must be 'en' or 'zh' for article events.")
        if page_key is not None:
            raise ValidationError("page_key must be null for article events.")

    return ViewEvent(
        scope=scope,
        page_key=page_key,
        article_id=article_id,
        lang=lang,
        visitor_id=visitor_id,
        domain=domain,
    )


def hash_visitor_id(visitor_id: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), visitor_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def encode_cursor_offset(offset: int | None) -> str | None:
    if offset is None:
        return None
    return urlsafe_b64encode(str(offset).encode("utf-8")).decode("ascii")


def decode_cursor_offset(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        return max(0, int(raw))
    except Exception as exc:  # pragma: no cover - defensive path
        raise ValidationError("cursor is invalid.") from exc


class DynamoCollectorStore:
    def __init__(
        self,
        *,
        counters_table_name: str,
        uniques_table_name: str,
        dynamodb_resource: Any | None = None,
        dynamodb_client: Any | None = None,
    ) -> None:
        self._resource = dynamodb_resource or boto3.resource("dynamodb")
        self._client = dynamodb_client or self._resource.meta.client
        self.counters_table_name = counters_table_name
        self.uniques_table_name = uniques_table_name
        self.counters_table = self._resource.Table(counters_table_name)
        self.uniques_table = self._resource.Table(uniques_table_name)

    def _claim_unique(
        self,
        *,
        entity_key: str,
        day_key: str,
        hashed_visitor_id: str,
        expires_at: int,
    ) -> bool:
        try:
            self.uniques_table.put_item(
                Item={
                    "pk": f"ENTITY#{entity_key}#{day_key}",
                    "sk": f"VISITOR#{hashed_visitor_id}",
                    "expire_at": expires_at,
                },
                ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
            )
            return True
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code")
            if code == "ConditionalCheckFailedException":
                return False
            raise RuntimeError(
                f"Failed to claim unique visitor for {entity_key} on {day_key}: "
                f"{code or 'UnknownError'}: {error.get('Message', 'No message returned')}"
            ) from exc

    def _increment_counter(
        self,
        *,
        entity_key: str,
        day_key: str,
        day_value: str,
        entity_type: str,
        entity_id: str,
        lang: str | None,
        domain: str | None,
        unique_increment: int,
    ) -> None:
        try:
            self.counters_table.update_item(
                Key={
                    "pk": entity_key,
                    "sk": day_key,
                },
                UpdateExpression=(
                    "SET entity_type = :entity_type, entity_id = :entity_id, #lang = :lang, "
                    "#date = :date, gsi1pk = :gsi1pk, gsi1sk = :gsi1sk, #domain = :domain "
                    "ADD #views :views, #unique_visitors :unique_visitors"
                ),
                ExpressionAttributeNames={
                    "#date": "date",
                    "#domain": "domain",
                    "#lang": "lang",
                    "#unique_visitors": "unique_visitors",
                    "#views": "views",
                },
                ExpressionAttributeValues={
                    ":date": day_value,
                    ":domain": domain,
                    ":entity_id": entity_id,
                    ":entity_type": entity_type,
                    ":gsi1pk": day_key,
                    ":gsi1sk": entity_key,
                    ":lang": lang,
                    ":unique_visitors": unique_increment,
                    ":views": 1,
                },
            )
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code")
            raise RuntimeError(
                f"Failed to update counter for {entity_key} on {day_key}: "
                f"{code or 'UnknownError'}: {error.get('Message', 'No message returned')}"
            ) from exc

    def record_view(
        self,
        event: ViewEvent,
        *,
        hashed_visitor_id: str,
        day: date,
        uniques_ttl_days: int,
    ) -> dict[str, bool]:
        day_value = day.isoformat()
        day_key = f"DAY#{day_value}"
        expires_at = int(
            datetime.combine(day + timedelta(days=uniques_ttl_days), time.min, tzinfo=timezone.utc).timestamp()
        )

        entity_unique_key = event.entity_key
        site_domain_unique_key = f"SITE#ALL#{event.domain}"
        site_combined_unique_key = "SITE#ALL"
        counter_targets = [
            {
                "entity_key": event.entity_key,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "lang": event.lang,
                "domain": event.domain,
            },
            {
                "entity_key": f"SITE#ALL#{event.domain}",
                "entity_type": "site",
                "entity_id": "ALL",
                "lang": None,
                "domain": event.domain,
            },
            {
                "entity_key": "SITE#ALL",
                "entity_type": "site",
                "entity_id": "ALL",
                "lang": None,
                "domain": None,
            },
        ]

        entity_unique = self._claim_unique(
            entity_key=entity_unique_key,
            day_key=day_key,
            hashed_visitor_id=hashed_visitor_id,
            expires_at=expires_at,
        )
        site_domain_unique = self._claim_unique(
            entity_key=site_domain_unique_key,
            day_key=day_key,
            hashed_visitor_id=hashed_visitor_id,
            expires_at=expires_at,
        )
        site_combined_unique = self._claim_unique(
            entity_key=site_combined_unique_key,
            day_key=day_key,
            hashed_visitor_id=hashed_visitor_id,
            expires_at=expires_at,
        )

        result = {
            "entity_unique": entity_unique,
            "site_unique": site_domain_unique,
        }

        unique_flags = [entity_unique, site_domain_unique, site_combined_unique]
        for target, is_unique in zip(counter_targets, unique_flags, strict=True):
            self._increment_counter(
                entity_key=target["entity_key"],
                day_key=day_key,
                day_value=day_value,
                entity_type=target["entity_type"],
                entity_id=target["entity_id"],
                lang=target["lang"],
                domain=target["domain"],
                unique_increment=1 if is_unique else 0,
            )

        return result


def handle_collect_request(
    event: dict[str, Any],
    *,
    settings: Settings,
    store: DynamoCollectorStore,
    now: datetime | None = None,
) -> dict[str, Any]:
    request_context = event.get("requestContext", {})
    http = request_context.get("http", {})
    method = str(http.get("method", "")).upper()
    if method != "POST":
        return json_response(405, {"error": "Method not allowed."})

    try:
        body = event.get("body")
        if event.get("isBase64Encoded"):
            body = b64decode(str(body or "")).decode("utf-8")
        payload = parse_event_body(body)
        view_event = validate_view_event(payload)
    except ValidationError as exc:
        return json_response(400, {"error": str(exc)})

    effective_now = now or datetime.now(timezone.utc)
    hashed_visitor_id = hash_visitor_id(view_event.visitor_id, settings.visitor_hmac_secret)
    result = store.record_view(
        view_event,
        hashed_visitor_id=hashed_visitor_id,
        day=effective_now.date(),
        uniques_ttl_days=settings.uniques_ttl_days,
    )
    return json_response(
        202,
        {
            "accepted": True,
            "scope": view_event.scope,
            "entity_key": view_event.entity_key,
            "unique": result,
        },
    )
