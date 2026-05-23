from __future__ import annotations

import sys

from .samples import seed_sources as _seed_sources

sys.modules[__name__] = _seed_sources
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _seed_sources)
