from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..domain.common import json_ready

def write_json(path: Path, data: Any) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(json_ready(data), ensure_ascii=False, indent=2)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == serialized:
                return False
        except OSError:
            pass
    path.write_text(serialized, encoding="utf-8")
    return True


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
