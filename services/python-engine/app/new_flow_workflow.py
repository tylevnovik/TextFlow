from __future__ import annotations

import sys

from .workflow.definitions import new_flow as _new_flow

sys.modules[__name__] = _new_flow
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _new_flow)
