from __future__ import annotations

import sys

from .workflow import plugins as _plugins

sys.modules[__name__] = _plugins
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _plugins)
