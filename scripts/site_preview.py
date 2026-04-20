from __future__ import annotations

import argparse
import errno
import json
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5500
DEFAULT_PORT_SEARCH_LIMIT = 20
ROOT_DIR = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT_DIR / "site"
SITE_ENG_DIR = ROOT_DIR / "site-eng"
ENGINEER_PREFIX = "/engineer"
NO_STORE_PATHS = {
    "/data/analytics.config.json",
}


def build_json_body(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


class SitePreviewHandler(SimpleHTTPRequestHandler):
    eng_directory: str = ""

    def translate_path(self, path: str) -> str:
        """Route /engineer/* requests to site-eng/, everything else to site/."""
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean == ENGINEER_PREFIX or clean.startswith(ENGINEER_PREFIX + "/"):
            # Strip the /engineer prefix and serve from site-eng/
            stripped = clean[len(ENGINEER_PREFIX):] or "/"
            # Temporarily swap directory to serve from site-eng/
            original_directory = self.directory
            self.directory = self.eng_directory
            result = super().translate_path(stripped)
            self.directory = original_directory
            return result
        return super().translate_path(path)

    def end_headers(self) -> None:
        request_path = self.path.split("?", 1)[0]
        if request_path in NO_STORE_PATHS or request_path.startswith("/analytics-api/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        request_path = self.path.split("?", 1)[0]
        if request_path != "/analytics-api/collect":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown path.")
            return

        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        request_path = self.path.split("?", 1)[0]
        if request_path != "/analytics-api/collect":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown path.")
            return

        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length > 0:
            self.rfile.read(content_length)

        body = build_json_body(
            {
                "accepted": True,
                "message": "Collector request accepted by the local preview server.",
                "mode": "local-preview",
            }
        )
        self.send_response(HTTPStatus.ACCEPTED)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class PreviewHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the site/ directory as the local web root.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--port-search-limit",
        type=int,
        default=DEFAULT_PORT_SEARCH_LIMIT,
        help="How many sequential ports to try when the requested port is already in use.",
    )
    parser.add_argument("--site-dir", default=str(SITE_DIR))
    return parser.parse_args()


def create_server(
    *,
    host: str,
    port: int,
    port_search_limit: int,
    handler: partial[SitePreviewHandler],
) -> tuple[PreviewHTTPServer, int]:
    max_offset = max(0, port_search_limit)
    last_error: OSError | None = None

    for offset in range(max_offset + 1):
        candidate_port = port + offset
        try:
            return PreviewHTTPServer((host, candidate_port), handler), candidate_port
        except OSError as exc:
            last_error = exc
            if exc.errno != errno.EADDRINUSE:
                raise

    if last_error is not None:
        raise last_error

    raise RuntimeError("Failed to create the local preview server.")


def main() -> None:
    args = parse_args()
    site_dir = Path(args.site_dir).resolve()
    site_eng_dir = SITE_ENG_DIR.resolve()
    SitePreviewHandler.eng_directory = str(site_eng_dir)
    handler = partial(SitePreviewHandler, directory=str(site_dir))
    server, active_port = create_server(
        host=args.host,
        port=args.port,
        port_search_limit=args.port_search_limit,
        handler=handler,
    )
    if active_port != args.port:
        print(
            f"Requested port {args.port} is busy; using http://{args.host}:{active_port} instead."
        )
    print(f"Site preview listening on http://{args.host}:{active_port}")
    print(f"Static root: {site_dir}")
    print(f"Engineering root: {site_eng_dir}")
    print(f"Engineering section: http://{args.host}:{active_port}/engineer/")
    print(f"Analytics admin: http://{args.host}:{active_port}/admin/analytics.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
