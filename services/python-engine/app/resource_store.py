from __future__ import annotations

import sys

from .storage import resources as _resources

sys.modules[__name__] = _resources
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _resources)
