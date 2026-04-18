from __future__ import annotations

import ast
import io
import json
import sys

from app.cli import main
from app.service import serve


def configure_stdio_utf8() -> None:
    stream_settings = (
        ("stdout", "strict"),
        ("stderr", "backslashreplace"),
    )
    for stream_name, errors in stream_settings:
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue

        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors=errors)
            continue

        buffer = getattr(stream, "buffer", None)
        if buffer is not None:
            wrapped = io.TextIOWrapper(buffer, encoding="utf-8", errors=errors, write_through=True)
            setattr(sys, stream_name, wrapped)


def parse_service_payload(raw: str) -> dict[str, object]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = ast.literal_eval(raw)
    if not isinstance(payload, dict):
        raise ValueError("service payload must be an object")
    return payload

if __name__ == "__main__":
    configure_stdio_utf8()
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        if len(sys.argv) > 3:
            serve(host=sys.argv[2], port=int(sys.argv[3]))
        else:
            payload = parse_service_payload(sys.argv[2]) if len(sys.argv) > 2 else {}
            serve(host=payload.get("host", "127.0.0.1"), port=int(payload.get("port", 8765)))
    else:
        main()
