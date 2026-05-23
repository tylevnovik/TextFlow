from __future__ import annotations

import sys

from .ingestion import specs as _specs

sys.modules[__name__] = _specs
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _specs)
