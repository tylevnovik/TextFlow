from __future__ import annotations

import sys

from .analysis import technology as _technology

sys.modules[__name__] = _technology
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _technology)
