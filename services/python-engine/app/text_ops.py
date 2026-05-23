from __future__ import annotations

import sys

from .analysis import text as _text

sys.modules[__name__] = _text
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _text)
