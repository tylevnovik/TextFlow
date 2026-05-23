from __future__ import annotations

import sys

from .workflow import runner as _runner

sys.modules[__name__] = _runner
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _runner)
