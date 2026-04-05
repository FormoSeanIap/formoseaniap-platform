from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
DEFAULT_PATH = "/podcast-feed"
DEFAULT_TIMEOUT_SECONDS = 15
LOCAL_CONFIG_CANDIDATES = (
    Path(__file__).resolve().parent.parent / "site" / "data" / "podcasts.shows.json",
    Path(__file__).resolve().parent / "podcasts.shows.json",
)


@dataclass
class ProxyResponse:
    status_code: int
    content_type: str
    body: bytes


class ProxyError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def default_config_path() -> Path:
    env_path = os.environ.get("PODCAST_SHOWS_CONFIG", "").strip()
    if env_path:
        return Path(env_path)

    for candidate in LOCAL_CONFIG_CANDIDATES:
        if candidate.exists():
            return candidate

    return LOCAL_CONFIG_CANDIDATES[0]


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    resolved_path = Path(config_path) if config_path else default_config_path()
    return json.loads(resolved_path.read_text(encoding="utf-8"))


def resolve_show_feed_url(config: dict[str, Any], show_id: str) -> str:
    shows = config.get("shows", [])
    for show in shows:
        if str(show.get("id", "")).strip() != show_id:
            continue
        feed_url = str(show.get("feed_url", "")).strip()
        if not feed_url:
            raise ProxyError(HTTPStatus.BAD_REQUEST, f"Feed URL is not configured for show_id '{show_id}'.")
        return feed_url
    raise ProxyError(HTTPStatus.NOT_FOUND, f"Unknown show_id '{show_id}'.")


def fetch_feed_bytes(feed_url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> ProxyResponse:
    request = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "formoseaniap-podcast-proxy/1.0",
            "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            content_type = response.headers.get_content_type() or "application/xml"
            return ProxyResponse(
                status_code=HTTPStatus.OK,
                content_type=content_type,
                body=body,
            )
    except urllib.error.HTTPError as exc:
        raise ProxyError(HTTPStatus.BAD_GATEWAY, f"Upstream feed request failed with HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise ProxyError(HTTPStatus.BAD_GATEWAY, f"Upstream feed request failed: {exc.reason}.") from exc


def build_success_headers(content_type: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Cache-Control": "public, max-age=300",
        "Content-Type": content_type,
    }


def build_error_body(message: str) -> bytes:
    payload = {"error": message}
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def proxy_feed(show_id: str, config_path: str | Path | None = None) -> ProxyResponse:
    if not show_id:
        raise ProxyError(HTTPStatus.BAD_REQUEST, "Missing required query parameter 'show_id'.")

    config = load_config(config_path)
    feed_url = resolve_show_feed_url(config, show_id)
    return fetch_feed_bytes(feed_url)


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if str(event.get("requestContext", {}).get("http", {}).get("method", "")).upper() == "OPTIONS":
        return {
            "statusCode": HTTPStatus.NO_CONTENT,
            "headers": build_success_headers("application/json"),
            "body": "",
        }

    params = event.get("queryStringParameters") or {}
    show_id = str(params.get("show_id", "")).strip()

    try:
        proxied = proxy_feed(show_id)
        return {
            "statusCode": proxied.status_code,
            "headers": build_success_headers(proxied.content_type),
            "body": proxied.body.decode("utf-8", errors="replace"),
        }
    except ProxyError as exc:
        return {
            "statusCode": exc.status_code,
            "headers": build_success_headers("application/json"),
            "body": build_error_body(exc.message).decode("utf-8"),
        }


class PodcastProxyHandler(BaseHTTPRequestHandler):
    config_path: Path = default_config_path()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        for (header, value) in build_success_headers("application/json").items():
            self.send_header(header, value)
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle_feed_request(send_body=False)

    def do_GET(self) -> None:  # noqa: N802
        self._handle_feed_request(send_body=True)

    def _handle_feed_request(self, *, send_body: bool) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != DEFAULT_PATH:
            self._send_error(HTTPStatus.NOT_FOUND, "Unknown path.")
            return

        params = urllib.parse.parse_qs(parsed.query)
        show_id = str(params.get("show_id", [""])[0]).strip()

        try:
            proxied = proxy_feed(show_id, self.config_path)
            self.send_response(proxied.status_code)
            for (header, value) in build_success_headers(proxied.content_type).items():
                self.send_header(header, value)
            self.end_headers()
            if send_body:
                self.wfile.write(proxied.body)
        except ProxyError as exc:
            self._send_error(exc.status_code, exc.message)

    def _send_error(self, status_code: int, message: str) -> None:
        body = build_error_body(message)
        self.send_response(status_code)
        for (header, value) in build_success_headers("application/json").items():
            self.send_header(header, value)
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local podcast RSS proxy for SoundOn feeds.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--config", default=str(default_config_path()))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    PodcastProxyHandler.config_path = Path(args.config)
    server = ThreadingHTTPServer((args.host, args.port), PodcastProxyHandler)
    print(f"Podcast proxy listening on http://{args.host}:{args.port}{DEFAULT_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
