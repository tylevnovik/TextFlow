from __future__ import annotations

import sys

from .workflow import compilers as _compilers

sys.modules[__name__] = _compilers
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _compilers)
