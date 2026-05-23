from __future__ import annotations

import sys

from .samples import bundled_workspace as _bundled_workspace

sys.modules[__name__] = _bundled_workspace
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _bundled_workspace)
