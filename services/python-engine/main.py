from __future__ import annotations

import ast
import io
import json
from multiprocessing import freeze_support
import sys


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


def run_entrypoint() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        from app.api.service import serve

        if len(sys.argv) > 3:
            serve(host=sys.argv[2], port=int(sys.argv[3]))
        else:
            payload = parse_service_payload(sys.argv[2]) if len(sys.argv) > 2 else {}
            serve(host=payload.get("host", "127.0.0.1"), port=int(payload.get("port", 8765)))
        return

    from app.api.actions.dispatcher import main

    main()

if __name__ == "__main__":
    freeze_support()
    configure_stdio_utf8()
    run_entrypoint()
