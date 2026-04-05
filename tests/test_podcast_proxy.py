import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.podcast_proxy import (
    ProxyError,
    ProxyResponse,
    lambda_handler,
    load_config,
    resolve_show_feed_url,
)


class PodcastProxyConfigTests(unittest.TestCase):
    def test_load_config_reads_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "podcasts.shows.json"
            config_path.write_text(json.dumps({"shows": [{"id": "demo", "feed_url": "https://example.com/feed.xml"}]}), encoding="utf-8")

            loaded = load_config(config_path)

        self.assertEqual(loaded["shows"][0]["id"], "demo")

    def test_resolve_show_feed_url_returns_matching_feed(self) -> None:
        config = {"shows": [{"id": "demo", "feed_url": "https://example.com/feed.xml"}]}

        feed_url = resolve_show_feed_url(config, "demo")

        self.assertEqual(feed_url, "https://example.com/feed.xml")

    def test_resolve_show_feed_url_raises_for_unknown_show(self) -> None:
        config = {"shows": [{"id": "demo", "feed_url": "https://example.com/feed.xml"}]}

        with self.assertRaises(ProxyError) as ctx:
            resolve_show_feed_url(config, "missing")

        self.assertEqual(ctx.exception.status_code, 404)


class PodcastProxyLambdaTests(unittest.TestCase):
    @patch("scripts.podcast_proxy.proxy_feed")
    def test_lambda_handler_returns_xml_body(self, mock_proxy_feed) -> None:
        mock_proxy_feed.return_value = ProxyResponse(
            status_code=200,
            content_type="application/xml",
            body=b"<rss></rss>",
        )

        response = lambda_handler(
            {"queryStringParameters": {"show_id": "demo"}},
            None,
        )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"]["Access-Control-Allow-Origin"], "*")
        self.assertEqual(response["body"], "<rss></rss>")

    @patch("scripts.podcast_proxy.proxy_feed")
    def test_lambda_handler_maps_proxy_errors_to_json(self, mock_proxy_feed) -> None:
        mock_proxy_feed.side_effect = ProxyError(400, "Missing required query parameter 'show_id'.")

        response = lambda_handler({"queryStringParameters": {}}, None)

        self.assertEqual(response["statusCode"], 400)
        self.assertIn("error", response["body"])
