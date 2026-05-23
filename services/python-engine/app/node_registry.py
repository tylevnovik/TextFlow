from __future__ import annotations

import sys

from .workflow import registry as _registry

sys.modules[__name__] = _registry
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _registry)
