# -*- coding: utf-8 -*-
"""`python -m dust_hazard_mcp` —— 自检入口。

只做两件事：列出工具、跑一遍状态机冒烟。完整的四个调试用例
（含中文字段、render 全文比对）请用 `python tests/test_mcp.py`。
"""

import sys


def main():
    from .tools import ENGINE_VERSION, TOOLS, call_tool, tools_manifest

    print("engine: %s" % ENGINE_VERSION)
    print("tools : %s" % ", ".join(t["name"] for t in tools_manifest()))
    print("-" * 58)

    # 用 clause_ids 指定条款，避免依赖中文领域名，保证任何控制台编码下都能跑
    cases = [
        ("no industry, no clause -> need_industry",
         {"payload": {"industry": "", "facts": {}}}, "need_industry"),
        ("clause given, no facts    -> describe",
         {"clause_ids": ["DUST-10-001"], "facts": {}}, "describe"),
        ("clause + matching fact   -> hit",
         {"clause_ids": ["DUST-10-006"],
          "facts": {"dust_collector.dust_kind": "wood",
                    "dust_collector.no_ash_discharge": True}}, "hit"),
        ("clause + wrong value     -> miss",
         {"clause_ids": ["DUST-10-006"],
          "facts": {"dust_collector.dust_kind": "wood",
                    "dust_collector.no_ash_discharge": False}}, "miss"),
        ("unknown clause id        -> need_industry",
         {"clause_ids": ["DUST-99-999"], "facts": {}}, "need_industry"),
        ("partial facts            -> ask",
         {"clause_ids": ["DUST-10-006"],
          "facts": {"dust_collector.dust_kind": "wood"}}, "ask"),
    ]

    bad = 0
    for label, args, expect in cases:
        r = call_tool("judge", args)
        ok = r.get("stage") == expect
        bad += 0 if ok else 1
        print(("OK   " if ok else "FAIL ") + "%-42s stage=%-14s verdict=%s"
              % (label, r.get("stage"), r.get("verdict")))

    print("-" * 58)
    print("tools=%d smoke_failed=%d" % (len(TOOLS), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
