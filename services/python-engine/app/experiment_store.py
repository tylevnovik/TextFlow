from __future__ import annotations

import sys

from .storage import experiments as _experiments

sys.modules[__name__] = _experiments
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _experiments)
