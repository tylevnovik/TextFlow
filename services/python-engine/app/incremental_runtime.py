from __future__ import annotations

import sys

from .workflow.runtime import incremental as _incremental

sys.modules[__name__] = _incremental
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _incremental)
