from __future__ import annotations

import sys

from .api.actions import dispatcher as _dispatcher

if __name__ == "__main__":
    _dispatcher.main()
else:
    sys.modules[__name__] = _dispatcher
    setattr(sys.modules[__package__], __name__.rpartition(".")[2], _dispatcher)
