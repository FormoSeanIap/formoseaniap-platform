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
    parse_domain_filter,
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
        self.items = {} if items is None else items

    def get_item(self, *, Key, ConsistentRead=False):  # noqa: N803
        del ConsistentRead
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": dict(item)} if item is not None else {}

    def put_item(self, *, Item, ConditionExpression):  # noqa: N803
        assert ConditionExpression == "attribute_not_exists(pk) AND attribute_not_exists(sk)"
        key = (Item["pk"], Item["sk"])
        if key in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Conditional failed"}},
                "PutItem",
            )
        self.items[key] = dict(Item)
        return {}

    def update_item(self, *, Key, UpdateExpression, ExpressionAttributeNames, ExpressionAttributeValues):  # noqa: N803
        assert "ADD #views :views, #unique_visitors :unique_visitors" in UpdateExpression
        key = (Key["pk"], Key["sk"])
        current = self.items.setdefault(key, {"pk": Key["pk"], "sk": Key["sk"], "views": 0, "unique_visitors": 0})
        current["entity_type"] = ExpressionAttributeValues[":entity_type"]
        current["entity_id"] = ExpressionAttributeValues[":entity_id"]
        current["lang"] = ExpressionAttributeValues[":lang"]
        current["domain"] = ExpressionAttributeValues[":domain"]
        current["date"] = ExpressionAttributeValues[":date"]
        current["gsi1pk"] = ExpressionAttributeValues[":gsi1pk"]
        current["gsi1sk"] = ExpressionAttributeValues[":gsi1sk"]
        current["views"] = int(current.get("views") or 0) + int(ExpressionAttributeValues[":views"])
        current["unique_visitors"] = int(current.get("unique_visitors") or 0) + int(
            ExpressionAttributeValues[":unique_visitors"]
        )
        return {"Attributes": dict(current)}


class FakeDynamoClient:
    def __init__(self, counters, uniques):
        self.counters = counters
        self.uniques = uniques

    def _deserialize_map(self, value):
        return {key: DESERIALIZER.deserialize(item) for key, item in value.items()}


class FakeDynamoResource:
    def __init__(self):
        self.counters = {}
        self.uniques = FakeDynamoTable()
        self.meta = type("Meta", (), {"client": FakeDynamoClient(self.counters, self.uniques)})()

    def Table(self, name):  # noqa: N802
        if name == "analytics_daily_counters":
            return FakeDynamoTable(self.counters)
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
                "domain": "main",
            }
        )

        self.assertEqual(event.entity_key, "PAGE#home#main")
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
                    "domain": "main",
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
                        "domain": "main",
                    }
                ),
                "requestContext": {"http": {"method": "POST"}},
            },
            settings=settings,
            store=store,
            now=datetime(2026, 4, 12, 1, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(response["statusCode"], 202)
        self.assertEqual(store.calls[0]["entity_key"], "ARTICLE#demo-article#zh#main")
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
                "domain": "main",
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
        entity_counter = fake_resource.counters[("ARTICLE#demo-article#en#main", "DAY#2026-04-12")]
        site_domain_counter = fake_resource.counters[("SITE#ALL#main", "DAY#2026-04-12")]
        site_combined_counter = fake_resource.counters[("SITE#ALL", "DAY#2026-04-12")]
        self.assertEqual(entity_counter["views"], 2)
        self.assertEqual(entity_counter["unique_visitors"], 1)
        self.assertEqual(entity_counter["domain"], "main")
        self.assertEqual(site_domain_counter["views"], 2)
        self.assertEqual(site_domain_counter["unique_visitors"], 1)
        self.assertEqual(site_domain_counter["domain"], "main")
        self.assertEqual(site_combined_counter["views"], 2)
        self.assertIsNone(site_combined_counter["domain"])

    def test_record_view_aliases_reserved_views_attribute(self):
        fake_resource = FakeDynamoResource()
        store = DynamoCollectorStore(
            counters_table_name="analytics_daily_counters",
            uniques_table_name="analytics_daily_uniques",
            dynamodb_resource=fake_resource,
            dynamodb_client=fake_resource.meta.client,
        )
        event = validate_view_event(
            {
                "scope": "page",
                "page_key": "home",
                "article_id": None,
                "lang": None,
                "visitor_id": "123e4567-e89b-12d3-a456-426614174000",
                "domain": "main",
            }
        )

        result = store.record_view(
            event,
            hashed_visitor_id="visitor-b",
            day=date(2026, 4, 12),
            uniques_ttl_days=7,
        )

        self.assertEqual(result, {"entity_unique": True, "site_unique": True})
        entity_counter = fake_resource.counters[("PAGE#home#main", "DAY#2026-04-12")]
        self.assertEqual(entity_counter["views"], 1)

    def test_record_view_backfills_missing_counter_metrics(self):
        fake_resource = FakeDynamoResource()
        fake_resource.counters[("PAGE#home#main", "DAY#2026-04-12")] = {
            "pk": "PAGE#home#main",
            "sk": "DAY#2026-04-12",
            "entity_type": "page",
            "entity_id": "home",
            "lang": None,
            "domain": "main",
            "date": "2026-04-12",
            "gsi1pk": "DAY#2026-04-12",
            "gsi1sk": "PAGE#home#main",
        }
        fake_resource.counters[("SITE#ALL#main", "DAY#2026-04-12")] = {
            "pk": "SITE#ALL#main",
            "sk": "DAY#2026-04-12",
            "entity_type": "site",
            "entity_id": "ALL",
            "lang": None,
            "domain": "main",
            "date": "2026-04-12",
            "gsi1pk": "DAY#2026-04-12",
            "gsi1sk": "SITE#ALL#main",
        }
        fake_resource.counters[("SITE#ALL", "DAY#2026-04-12")] = {
            "pk": "SITE#ALL",
            "sk": "DAY#2026-04-12",
            "entity_type": "site",
            "entity_id": "ALL",
            "lang": None,
            "domain": None,
            "date": "2026-04-12",
            "gsi1pk": "DAY#2026-04-12",
            "gsi1sk": "SITE#ALL",
        }
        store = DynamoCollectorStore(
            counters_table_name="analytics_daily_counters",
            uniques_table_name="analytics_daily_uniques",
            dynamodb_resource=fake_resource,
            dynamodb_client=fake_resource.meta.client,
        )
        event = validate_view_event(
            {
                "scope": "page",
                "page_key": "home",
                "article_id": None,
                "lang": None,
                "visitor_id": "123e4567-e89b-12d3-a456-426614174000",
                "domain": "main",
            }
        )

        result = store.record_view(
            event,
            hashed_visitor_id="visitor-c",
            day=date(2026, 4, 12),
            uniques_ttl_days=7,
        )

        self.assertEqual(result, {"entity_unique": True, "site_unique": True})
        self.assertEqual(fake_resource.counters[("PAGE#home#main", "DAY#2026-04-12")]["views"], 1)
        self.assertEqual(fake_resource.counters[("PAGE#home#main", "DAY#2026-04-12")]["unique_visitors"], 1)


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


class AdminDomainFilterTests(unittest.TestCase):
    """Tests for domain filtering in admin API payload builders."""

    def test_parse_domain_filter_accepts_valid_domains(self):
        self.assertEqual(parse_domain_filter("main"), "main")
        self.assertEqual(parse_domain_filter("engineering"), "engineering")

    def test_parse_domain_filter_returns_none_when_omitted(self):
        self.assertIsNone(parse_domain_filter(None))
        self.assertIsNone(parse_domain_filter(""))

    def test_parse_domain_filter_rejects_invalid_value(self):
        with self.assertRaisesRegex(ValidationError, "domain must be 'main', 'engineering', or omitted"):
            parse_domain_filter("invalid")

    def test_overview_filter_by_main_with_mixed_data(self):
        reader = FakeAnalyticsReader(
            day_items={
                "2026-04-10": [
                    {"pk": "SITE#ALL", "entity_type": "site", "views": 10, "unique_visitors": 6},
                    {"pk": "SITE#ALL#main", "entity_type": "site", "views": 7, "unique_visitors": 4, "domain": "main"},
                    {"pk": "SITE#ALL#engineering", "entity_type": "site", "views": 3, "unique_visitors": 2, "domain": "engineering"},
                    {"pk": "ARTICLE#a#en#main", "entity_type": "article", "entity_id": "a", "lang": "en", "views": 5, "unique_visitors": 3, "domain": "main"},
                    {"pk": "ARTICLE#b#en#engineering", "entity_type": "article", "entity_id": "b", "lang": "en", "views": 2, "unique_visitors": 1, "domain": "engineering"},
                ],
            }
        )
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 10))

        payload = build_overview_payload(reader, date_range, domain_filter="main")

        self.assertEqual(payload["domain"], "main")
        self.assertEqual(payload["summary"]["site_views"], 7)
        self.assertEqual(payload["summary"]["site_unique_visitors"], 4)
        self.assertEqual(payload["summary"]["article_views"], 5)
        self.assertEqual(payload["summary"]["article_unique_visitors"], 3)

    def test_overview_filter_by_engineering(self):
        reader = FakeAnalyticsReader(
            day_items={
                "2026-04-10": [
                    {"pk": "SITE#ALL", "entity_type": "site", "views": 10, "unique_visitors": 6},
                    {"pk": "SITE#ALL#main", "entity_type": "site", "views": 7, "unique_visitors": 4, "domain": "main"},
                    {"pk": "SITE#ALL#engineering", "entity_type": "site", "views": 3, "unique_visitors": 2, "domain": "engineering"},
                    {"pk": "ARTICLE#a#en#main", "entity_type": "article", "entity_id": "a", "lang": "en", "views": 5, "unique_visitors": 3, "domain": "main"},
                    {"pk": "ARTICLE#b#en#engineering", "entity_type": "article", "entity_id": "b", "lang": "en", "views": 2, "unique_visitors": 1, "domain": "engineering"},
                ],
            }
        )
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 10))

        payload = build_overview_payload(reader, date_range, domain_filter="engineering")

        self.assertEqual(payload["domain"], "engineering")
        self.assertEqual(payload["summary"]["site_views"], 3)
        self.assertEqual(payload["summary"]["site_unique_visitors"], 2)
        self.assertEqual(payload["summary"]["article_views"], 2)
        self.assertEqual(payload["summary"]["article_unique_visitors"], 1)

    def test_overview_no_filter_shows_combined(self):
        reader = FakeAnalyticsReader(
            day_items={
                "2026-04-10": [
                    {"pk": "SITE#ALL", "entity_type": "site", "views": 10, "unique_visitors": 6},
                    {"pk": "SITE#ALL#main", "entity_type": "site", "views": 7, "unique_visitors": 4, "domain": "main"},
                    {"pk": "SITE#ALL#engineering", "entity_type": "site", "views": 3, "unique_visitors": 2, "domain": "engineering"},
                    {"pk": "ARTICLE#a#en#main", "entity_type": "article", "entity_id": "a", "lang": "en", "views": 5, "unique_visitors": 3, "domain": "main"},
                    {"pk": "ARTICLE#b#en#engineering", "entity_type": "article", "entity_id": "b", "lang": "en", "views": 2, "unique_visitors": 1, "domain": "engineering"},
                ],
            }
        )
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 10))

        payload = build_overview_payload(reader, date_range)

        self.assertNotIn("domain", payload)
        self.assertEqual(payload["summary"]["site_views"], 10)
        self.assertEqual(payload["summary"]["site_unique_visitors"], 6)
        # Combined includes all article items
        self.assertEqual(payload["summary"]["article_views"], 7)
        self.assertEqual(payload["summary"]["article_unique_visitors"], 4)

    def test_overview_backward_compat_old_items_treated_as_main(self):
        """Old-format items without a domain attribute should be treated as 'main'."""
        reader = FakeAnalyticsReader(
            day_items={
                "2026-04-10": [
                    {"pk": "SITE#ALL#main", "entity_type": "site", "views": 4, "unique_visitors": 2, "domain": "main"},
                    # Old-format article item without domain attribute
                    {"pk": "ARTICLE#old#en", "entity_type": "article", "entity_id": "old", "lang": "en", "views": 3, "unique_visitors": 1},
                    {"pk": "ARTICLE#new#en#engineering", "entity_type": "article", "entity_id": "new", "lang": "en", "views": 2, "unique_visitors": 1, "domain": "engineering"},
                ],
            }
        )
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 10))

        payload = build_overview_payload(reader, date_range, domain_filter="main")

        # Old item (no domain) should be treated as main
        self.assertEqual(payload["summary"]["article_views"], 3)
        self.assertEqual(payload["summary"]["article_unique_visitors"], 1)

    def test_articles_filter_by_domain(self):
        reader = FakeAnalyticsReader(
            day_items={
                "2026-04-10": [
                    {"entity_type": "article", "entity_id": "main-art", "lang": "en", "views": 4, "unique_visitors": 3, "domain": "main"},
                    {"entity_type": "article", "entity_id": "eng-art", "lang": "en", "views": 2, "unique_visitors": 1, "domain": "engineering"},
                ]
            }
        )
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 10))

        main_payload = build_articles_payload(reader, date_range, group_mode="combined", limit=50, cursor=None, domain_filter="main")
        eng_payload = build_articles_payload(reader, date_range, group_mode="combined", limit=50, cursor=None, domain_filter="engineering")

        self.assertEqual(len(main_payload["items"]), 1)
        self.assertEqual(main_payload["items"][0]["article_id"], "main-art")
        self.assertEqual(len(eng_payload["items"]), 1)
        self.assertEqual(eng_payload["items"][0]["article_id"], "eng-art")

    def test_articles_no_filter_shows_all(self):
        reader = FakeAnalyticsReader(
            day_items={
                "2026-04-10": [
                    {"entity_type": "article", "entity_id": "main-art", "lang": "en", "views": 4, "unique_visitors": 3, "domain": "main"},
                    {"entity_type": "article", "entity_id": "eng-art", "lang": "en", "views": 2, "unique_visitors": 1, "domain": "engineering"},
                ]
            }
        )
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 10))

        payload = build_articles_payload(reader, date_range, group_mode="combined", limit=50, cursor=None)

        self.assertEqual(len(payload["items"]), 2)

    def test_article_detail_includes_domain_breakdown(self):
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 10))
        reader = FakeAnalyticsReader(
            entity_items={
                "ARTICLE#demo#en#main": [
                    {"date": "2026-04-10", "views": 3, "unique_visitors": 2, "domain": "main"},
                ],
                "ARTICLE#demo#en#engineering": [
                    {"date": "2026-04-10", "views": 1, "unique_visitors": 1, "domain": "engineering"},
                ],
                "ARTICLE#demo#zh#main": [
                    {"date": "2026-04-10", "views": 2, "unique_visitors": 2, "domain": "main"},
                ],
            }
        )

        payload = build_article_detail_payload(reader, date_range, article_id="demo")

        self.assertEqual(payload["combined"]["views"], 6)
        self.assertEqual(payload["by_language"]["en"]["views"], 4)
        self.assertEqual(payload["by_language"]["zh"]["views"], 2)
        self.assertEqual(payload["by_domain"]["main"]["views"], 5)
        self.assertEqual(payload["by_domain"]["engineering"]["views"], 1)
        # Daily should also have by_domain
        self.assertEqual(payload["daily"][0]["by_domain"]["main"]["views"], 5)
        self.assertEqual(payload["daily"][0]["by_domain"]["engineering"]["views"], 1)

    def test_article_detail_with_domain_filter(self):
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 10))
        reader = FakeAnalyticsReader(
            entity_items={
                "ARTICLE#demo#en#main": [
                    {"date": "2026-04-10", "views": 3, "unique_visitors": 2, "domain": "main"},
                ],
                "ARTICLE#demo#en#engineering": [
                    {"date": "2026-04-10", "views": 1, "unique_visitors": 1, "domain": "engineering"},
                ],
            }
        )

        payload = build_article_detail_payload(reader, date_range, article_id="demo", domain_filter="main")

        self.assertEqual(payload["domain"], "main")
        self.assertEqual(payload["combined"]["views"], 3)
        self.assertEqual(payload["by_language"]["en"]["views"], 3)

    def test_article_detail_backward_compat_old_format_keys(self):
        """Old-format entity keys (no domain suffix) should be included and treated as main."""
        date_range = DateRange(start=date(2026, 4, 10), end=date(2026, 4, 10))
        reader = FakeAnalyticsReader(
            entity_items={
                # Old-format key without domain suffix
                "ARTICLE#legacy#en": [
                    {"date": "2026-04-10", "views": 5, "unique_visitors": 3},
                ],
            }
        )

        # No filter — old items should be included
        payload = build_article_detail_payload(reader, date_range, article_id="legacy")
        self.assertEqual(payload["combined"]["views"], 5)
        self.assertEqual(payload["by_domain"]["main"]["views"], 5)

        # Filter by main — old items should be included
        payload_main = build_article_detail_payload(reader, date_range, article_id="legacy", domain_filter="main")
        self.assertEqual(payload_main["combined"]["views"], 5)

        # Filter by engineering — old items should be excluded
        payload_eng = build_article_detail_payload(reader, date_range, article_id="legacy", domain_filter="engineering")
        self.assertEqual(payload_eng["combined"]["views"], 0)


if __name__ == "__main__":
    unittest.main()
