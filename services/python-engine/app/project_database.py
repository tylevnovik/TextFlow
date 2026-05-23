from __future__ import annotations

import sys

from .storage import database as _database

sys.modules[__name__] = _database
setattr(sys.modules[__package__], __name__.rpartition(".")[2], _database)
