from __future__ import annotations

import sys

from .domain import defaults as _defaults

sys.modules[__name__] = _defaults
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _defaults)
