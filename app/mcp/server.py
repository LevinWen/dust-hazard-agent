# -*- coding: utf-8 -*-
"""Compat entry: `python server.py` == `dust-hazard-mcp`.

Real implementation lives in dust_hazard_mcp/server.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dust_hazard_mcp.server import main  # noqa: E402

if __name__ == "__main__":
    main()