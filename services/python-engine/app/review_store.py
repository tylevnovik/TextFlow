from __future__ import annotations

import sys

from .storage import reviews as _reviews

sys.modules[__name__] = _reviews
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _reviews)
