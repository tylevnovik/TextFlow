from __future__ import annotations

import sys

from .storage import projects as _projects

sys.modules[__name__] = _projects
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _projects)
