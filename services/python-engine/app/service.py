from __future__ import annotations

import sys

from .api import service as _service

sys.modules[__name__] = _service
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _service)
