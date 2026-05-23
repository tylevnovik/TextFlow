from __future__ import annotations

import sys

from .storage import run_diff as _run_diff

sys.modules[__name__] = _run_diff
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _run_diff)
