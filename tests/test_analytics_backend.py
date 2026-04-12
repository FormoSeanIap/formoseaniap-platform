import json
import unittest
from datetime import date, datetime, timezone

from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError

from analytics_backend.admin import (
    DateRange,
    build_article_detail_payload,
    build_articles_payload,
    build_overview_payload,
    parse_groups_claim,
)
from analytics_backend.collector import (
    DynamoCollectorStore,
    ValidationError,
    handle_collect_request,
    hash_visitor_id,
    validate_view_event,
)
from analytics_backend.config import Settings


DESERIALIZER = TypeDeserializer()


class FakeDynamoTable:
    def __init__(self, items=None):
        self.items = items or {}

    def get_item(self, *, Key, ConsistentRead=False):  # noqa: N803
        del ConsistentRead
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": dict(item)} if item is not None else {}


class FakeDynamoClient:
    def __init__(self, counters, uniques):
        self.counters = counters
        self.uniques = uniques

    def _deserialize_map(self, value):
        return {key: DESERIALIZER.deserialize(item) for key, item in value.items()}

    def transact_write_items(self, *, TransactItems):  # noqa: N803
        pending_uniques = []

        for action in TransactItems:
            if "Put" in action:
                item = self._deserialize_map(action["Put"]["Item"])
                key = (item["pk"], item["sk"])
                if key in self.uniques.items:
                    raise ClientError(
                        {"Error": {"Code": "TransactionCanceledException", "Message": "Conditional failed"}},
                        "TransactWriteItems",
                    )
                pending_uniques.append((key, item))

        for key, item in pending_uniques:
            self.uniques.items[key] = item

        for action in TransactItems:
            if "Update" not in action:
                continue

            update = action["Update"]
            key = self._deserialize_map(update["Key"])
            attrs = self._deserialize_map(update["ExpressionAttributeValues"])
            item_key = (key["pk"], key["sk"])
            current = self.counters.setdefault(item_key, {"pk": key["pk"], "sk": key["sk"], "views": 0, "unique_visitors": 0})
            current["entity_type"] = attrs[":entity_type"]
            current["entity_id"] = attrs[":entity_id"]
            current["lang"] = attrs[":lang"]
            current["date"] = attrs[":date"]
            current["gsi1pk"] = attrs[":gsi1pk"]
            current["gsi1sk"] = attrs[":gsi1sk"]
            current["views"] += int(attrs[":views"])
            current["unique_visitors"] += int(attrs[":unique_visitors"])


class FakeDynamoResource:
    def __init__(self):
        self.counters = {}
        self.uniques = FakeDynamoTable()
        self.meta = type("Meta", (), {"client": FakeDynamoClient(self.counters, self.uniques)})()

    def Table(self, name):  # noqa: N802
        del name
        return self.uniques


class FakeCollectorStore:
    def __init__(self):
        self.calls = []

    def record_view(self, view_event, *, hashed_visitor_id, day, uniques_ttl_days):
        self.calls.append(
            {
                "entity_key": view_event.entity_key,
                "scope": view_event.scope,
                "day": day.isoformat(),
                "hashed_visitor_id": hashed_visitor_id,
                "uniques_ttl_days": uniques_ttl_days,
            }
        )
        return {"entity_unique": True, "site_unique": True}


class FakeAnalyticsReader:
    def __init__(self, day_items=None, entity_items=None):
        self.day_items = day_items or {}
        self.entity_items = entity_items or {}

    def query_day(self, day_value):
        return list(self.day_items.get(day_value.isoformat(), []))

    def query_entity_range(self, entity_key, date_range):
        del date_range
        return list(self.entity_items.get(entity_key, []))


class CollectorValidationTests(unittest.TestCase):
    def test_page_view_event_is_normalized(self):
        event = validate_view_event(
            {
                "scope": "page",
                "page_key": "home",
                "article_id": None,
                "lang": None,
                "visitor_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        )

        self.assertEqual(event.entity_key, "PAGE#home")
        self.assertEqual(event.entity_type, "page")
        self.assertEqual(event.entity_id, "home")

    def test_article_view_requires_lang_and_id(self):
        with self.assertRaisesRegex(ValidationError, "article_id is required"):
            validate_view_event(
                {
                    "scope": "article",
                    "page_key": None,
                    "article_id": None,
                    "lang": "en",
                    "visitor_id": "123e4567-e89b-12d3-a456-426614174000",
                }
            )

    def test_collect_handler_hashes_and_passes_event_to_store(self):
        settings = Settings(
            counters_table_name="analytics_daily_counters",
            uniques_table_name="analytics_daily_uniques",
            visitor_hmac_secret="top-secret",
            admin_group_name="analytics-admin",
            uniques_ttl_days=7,
        )
        store = FakeCollectorStore()

        response = handle_collect_request(
            {
                "body": json.dumps(
                    {
                        "scope": "article",
                        "page_key": None,
                        "article_id": "demo-article",
                        "lang": "zh",
                        "visitor_id": "123e4567-e89b-12d3-a456-426614174000",
                    }
                ),
                "requestContext": {"http": {"method": "POST"}},
            },
            settings=settings,
            store=store,
            now=datetime(2026, 4, 12, 1, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(response["statusCode"], 202)
        self.assertEqual(store.calls[0]["entity_key"], "ARTICLE#demo-article#zh")
        self.assertEqual(store.calls[0]["day"], "2026-04-12")
        self.assertEqual(store.calls[0]["hashed_visitor_id"], hash_visitor_id("123e4567-e89b-12d3-a456-426614174000", "top-secret"))


class CollectorStoreTests(unittest.TestCase):
    def test_record_view_dedupes_unique_visitors_per_day(self):
        fake_resource = FakeDynamoResource()
        store = DynamoCollectorStore(
            counters_table_name="analytics_daily_counters",
            uniques_table_name="analytics_daily_uniques",
            dynamodb_resource=fake_resource,
            dynamodb_client=fake_resource.meta.client,
        )
        event = validate_view_event(
            {
                "scope": "article",
                "page_key": None,
                "article_id": "demo-article",
                "lang": "en",
                "visitor_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        )

        first = store.record_view(
            event,
            hashed_visitor_id="visitor-a",
            day=date(2026, 4, 12),
            uniques_ttl_days=7,
        )
        second = store.record_view(
            event,
            hashed_visitor_id="visitor-a",
            day=date(2026, 4, 12),
            uniques_ttl_days=7,
        )

        self.assertEqual(first, {"entity_unique": True, "site_unique": True})
        self.assertEqual(second, {"entity_unique": False, "site_unique": False})
        entity_counter = fake_resource.counters[("ARTICLE#demo-article#en", "DAY#2026-04-12")]
        site_counter = fake_resource.counters[("SITE#ALL", "DAY#2026-04-12")]
        self.assertEqual(entity_counter["views"], 2)
        self.assertEqual(entity_counter["unique_visitors"], 1)
        self.assertEqual(site_counter["views"], 2)
        self.assertEqual(site_counter["unique_visitors"], 1)


class AdminAggregationTests(unittest.TestCase):
    def test_build_overview_rolls_up_daily_metrics(self):
        reader = FakeAnalyticsReader(
            day_items={
                "2026-04-10": [
                    {"pk": "SITE#ALL", "entity_type": "site", "views": 8, "unique_visitors": 4},
                    {"pk": "ARTICLE#a#en", "entity_type": "article", "entity_id": "a", "lang": "en", "views": 3, "unique_visitors": 2},
                    {"pk": "ARTICLE#a#zh", "entity_type": "article", "entity_id": "a", "lang": "zh", "views": 1, "unique_visitors": 1},
                ],
                "2026-04-11": [
                    {"pk": "SITE#ALL", "entity_type": "site", "views": 5, "unique_visitors": 3},
                    {"pk": "ARTICLE#b#en", "entity_type": "article", "entity_id": "b", "lang": "en", "views": 2, "unique_visitors": 1},
                ],
            }
        )

        payload = build_overview_payload(reader, DateRange(start=date(2026, 4, 10), end=date(2026, 4, 11)))

        self.assertEqual(payload["summary"]["site_views"], 13)
        self.assertEqual(payload["summary"]["site_unique_visitors"], 7)
        self.assertEqual(payload["summary"]["article_views"], 6)
        self.assertEqual(payload["summary"]["article_unique_visitors"], 4)
        self.assertEqual(len(payload["daily"]), 2)

    def test_build_articles_supports_combined_and_variant_grouping(self):
        reader = FakeAnalyticsReader(
            day_items={
                "2026-04-10": [
                    {"entity_type": "article", "entity_id": "demo", "lang": "en", "views": 4, "unique_visitors": 3},
                    {"entity_type": "article", "entity_id": "demo", "lang": "zh", "views": 2, "unique_visitors": 2},
                    {"entity_type": "article", "entity_id": "other", "lang": "en", "views": 1, "unique_visitors": 1},
                ]
            }
        )
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 10))

        combined = build_articles_payload(reader, date_range, group_mode="combined", limit=50, cursor=None)
        variant = build_articles_payload(reader, date_range, group_mode="variant", limit=50, cursor=None)

        self.assertEqual(combined["items"][0]["article_id"], "demo")
        self.assertEqual(combined["items"][0]["views"], 6)
        self.assertEqual(combined["items"][0]["languages"]["en"]["views"], 4)
        self.assertEqual(len(variant["items"]), 3)
        self.assertEqual(variant["items"][0]["lang"], "en")

    def test_build_article_detail_rolls_up_language_variants(self):
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 11))
        reader = FakeAnalyticsReader(
            entity_items={
                "ARTICLE#demo#en": [
                    {"date": "2026-04-10", "views": 3, "unique_visitors": 2},
                    {"date": "2026-04-11", "views": 1, "unique_visitors": 1},
                ],
                "ARTICLE#demo#zh": [
                    {"date": "2026-04-10", "views": 2, "unique_visitors": 2},
                ],
            }
        )

        payload = build_article_detail_payload(reader, date_range, article_id="demo")

        self.assertEqual(payload["combined"]["views"], 6)
        self.assertEqual(payload["by_language"]["en"]["views"], 4)
        self.assertEqual(payload["by_language"]["zh"]["views"], 2)
        self.assertEqual(payload["daily"][0]["combined"]["views"], 5)

    def test_parse_groups_claim_handles_cognito_string_lists(self):
        groups = parse_groups_claim({"cognito:groups": "[analytics-admin, editors]"})
        self.assertEqual(groups, ["analytics-admin", "editors"])


if __name__ == "__main__":
    unittest.main()
