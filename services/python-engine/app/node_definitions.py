from __future__ import annotations

import sys

from .workflow.definitions import builtin as _builtin

sys.modules[__name__] = _builtin
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _builtin)
