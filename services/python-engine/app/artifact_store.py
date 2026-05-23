from __future__ import annotations

import sys

from .storage import artifacts as _artifacts

sys.modules[__name__] = _artifacts
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _artifacts)
