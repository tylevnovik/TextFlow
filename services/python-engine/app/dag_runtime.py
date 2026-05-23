from __future__ import annotations

import sys

from .workflow.runtime import native as _native

sys.modules[__name__] = _native
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _native)
