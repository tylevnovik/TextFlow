from __future__ import annotations

import sys

from .workflow.runtime import support as _support

sys.modules[__name__] = _support
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _support)
