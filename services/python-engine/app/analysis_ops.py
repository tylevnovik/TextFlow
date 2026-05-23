from __future__ import annotations

import sys

from . import analysis as _analysis

sys.modules[__name__] = _analysis
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _analysis)
