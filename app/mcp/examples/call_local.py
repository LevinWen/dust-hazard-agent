# -*- coding: utf-8 -*-
"""
调用示例（进程内直调）：不经过 HTTP / MCP，直接 import 工具层
=============================================================

适合评测脚本、离线跑分、单元测试这类同进程场景。
和 HTTP 形态、MCP 形态调用的是同一份实现，结论必然一致。

用法：
    python examples/call_local.py
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import tools as tool_layer  # noqa: E402


def show(title, result, key=None):
    print("=" * 62)
    print(title)
    print("-" * 62)
    if key:
        print(result.get(key))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2)[:900])


def main():
    # 1. 最常用：一句现场描述整理成 facts 后判定
    r = tool_layer.call_tool("judge", {
        "facts": {"dust_collector.type": "dry",
                  "dust_collector.dust_kind": "wood",
                  "dust_collector.control_measures": ["vent"],
                  "dust_collector.no_ash_discharge": True},
        "industry": "粉尘涉爆",
    })
    show("[1] 判定：干式木粉尘 + 未装锁气卸灰", r, key="render")
    print("verdict=%s stage=%s checked=%s 命中=%s"
          % (r["verdict"], r["stage"], r["checked"],
             [h["clause_id"] for h in r["hits"]]))

    # 2. 信息不足时它不会猜，而是给追问
    r = tool_layer.call_tool("judge", {
        "facts": {"dust_collector.dust_kind": "wood"},
        "industry": "粉尘涉爆",
    })
    show("[2] 判定：信息不足 -> 待核实", r, key="render")
    print("ask_more=%s（还剩几项要问）" % r["ask_more"])

    # 3. 条款查询三件套
    r = tool_layer.call_tool("list_clauses", {"industry": "粉尘涉爆"})
    print("\n[3] 条款清单：共 %d 条 -> %s" % (r["total"],
          "、".join(c["clause_id"] for c in r["clauses"])))

    r = tool_layer.call_tool("clause_detail", {"clause_id": "DUST-10-006"})
    print("[4] DUST-10-006 原文：%s" % r["source"]["original"])
    print("    需要证据：%s" % "、".join(r["evidence_required"]))

    r = tool_layer.call_tool("clause_search", {"text": "除尘器没装泄爆片"})
    print("[5] 现象 -> 候选条款：%s"
          % [(c["clause_id"], c["article"]) for c in r["candidates"]])

    # 4. 出文书（模板 + 要素填充）
    r = tool_layer.call_tool("render_doc", {
        "doc_type": "现场检查记录",
        "industry": "粉尘涉爆",
        "facts": {"dust.cleaning_not_implemented": True},
        "meta": {"企业名称": "某木质家具厂", "检查时间": "2026-11-23",
                 "检查地点": "一号生产车间", "执法人员": "张三、李四",
                 "被检查人": "王五"},
    })
    show("[6] 文书草稿", r, key="draft")
    print("要素校验：%s" % json.dumps(r["checks"], ensure_ascii=False))

    print("\n全部完成。工具数 %d。" % len(tool_layer.TOOLS))


if __name__ == "__main__":
    main()
