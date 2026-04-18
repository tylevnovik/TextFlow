from __future__ import annotations

import io
import sys
from contextlib import contextmanager

from main import configure_stdio_utf8, parse_service_payload


@contextmanager
def patched_stdio(stdout, stderr):
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = stdout
    sys.stderr = stderr
    try:
        yield
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def test_configure_stdio_utf8_reconfigures_text_wrappers():
    stdout = io.TextIOWrapper(io.BytesIO(), encoding="gbk")
    stderr = io.TextIOWrapper(io.BytesIO(), encoding="gbk")

    with patched_stdio(stdout, stderr):
        configure_stdio_utf8()
        assert sys.stdout.encoding.lower().replace("-", "") == "utf8"
        assert sys.stderr.encoding.lower().replace("-", "") == "utf8"


def test_parse_service_payload_accepts_json_and_literal_styles():
    assert parse_service_payload('{"host":"127.0.0.1","port":8899}') == {"host": "127.0.0.1", "port": 8899}
    assert parse_service_payload("{'host': '127.0.0.1', 'port': 8899}") == {"host": "127.0.0.1", "port": 8899}
