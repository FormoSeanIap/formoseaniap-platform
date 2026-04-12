from __future__ import annotations

import json
from typing import Any


def json_response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "cache-control": "no-store",
            "content-type": "application/json; charset=utf-8",
        },
        "body": json.dumps(payload, separators=(",", ":"), ensure_ascii=True),
    }

