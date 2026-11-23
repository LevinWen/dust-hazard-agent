# -*- coding: utf-8 -*-
"""粉尘涉爆重大事故隐患判定工具集。

对外只需要两个入口：

    from dust_hazard_mcp import call_tool, TOOLS, tools_manifest

    r = call_tool("judge", {"facts": {...}, "industry": "粉尘涉爆"})

命令行：
    dust-hazard-mcp             启动 MCP 服务（stdio）
    dust-hazard-http            启动 HTTP 外壳
    python -m dust_hazard_mcp   跑冒烟用例
"""

__version__ = "1.0.0"

from .tools import (  # noqa: F401
    ENGINE_VERSION,
    FACT_FIELDS,
    TOOLS,
    call_tool,
    clause_check,
    clause_detail,
    clause_search,
    judge,
    list_clauses,
    render_doc,
    tools_manifest,
    validate_facts,
)
