from __future__ import annotations

import sys

from .analysis import graph as _graph

sys.modules[__name__] = _graph
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _graph)
