# -*- coding: utf-8 -*-
"""Compat entry: `python tools.py` runs the smoke test.

Real implementation lives in dust_hazard_mcp/tools.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dust_hazard_mcp.tools import *  # noqa: F401,F403
from dust_hazard_mcp.tools import TOOLS, call_tool, tools_manifest  # noqa: F401

if __name__ == "__main__":
    from dust_hazard_mcp.__main__ import main
    raise SystemExit(main())