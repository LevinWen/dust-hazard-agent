# -*- coding: utf-8 -*-
"""
远程 MCP 服务自测（不需要平台控制台，直接打隧道/线上地址）
==========================================================

用法：
    python tests/test_remote_mcp.py --base https://xxxx.app.lhr.life
    python tests/test_remote_mcp.py --base https://xxxx.hsk.top --token mytoken

它会依次跑：
    1. GET  /health                 服务存活
    2. POST /mcp initialize         握手 + 会话
    3. POST /mcp notifications      通知返回 202
    4. POST /mcp tools/list         六个工具
    5. POST /mcp tools/call ×5      判定三态 + 条款查询 + 出文书

全部通过会打印「全部通过」。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

OK, FAIL = [], []


def check(name, cond, detail=""):
    (OK if cond else FAIL).append(name)
    print(("  OK   " if cond else "  FAIL ") + name + ("" if cond else "   <- " + str(detail)[:160]))
    return cond


def post(base, payload, headers=None, timeout=60):
    req = urllib.request.Request(base.rstrip("/") + "/mcp",
                                 data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8")


def call(base, name, args, headers):
    s, h, b = post(base, {"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                          "params": {"name": name, "arguments": args}}, headers)
    if not b.strip():
        return s, None, b
    try:
        return s, json.loads(b), b
    except Exception:
        return s, None, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="MCP 服务根地址，如 https://xxx.app.lhr.life")
    ap.add_argument("--token", default="", help="若开启了 Bearer 鉴权则填")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    auth = {"Authorization": "Bearer " + a.token} if a.token else {}
    print("目标：%s\n" % base)

    print("[1] 存活检查")
    try:
        with urllib.request.urlopen(base + "/health", timeout=30) as r:
            health = json.loads(r.read().decode())
        check("GET /health 200", True)
        check("工具数 = 6", health.get("tools") == 6, health)
    except Exception as e:
        check("GET /health 200", False, e)
        print("\n链路不通，后面的测试没有意义。先确认：")
        print("  1) 本地 dust-hazard-http 是否在跑")
        print("  2) 隧道/穿透是否还在（地址变了要同步改平台 URL）")
        return 1

    print("[2] MCP 握手")
    s, h, b = post(base, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": "2024-11-05",
                                     "capabilities": {},
                                     "clientInfo": {"name": "remote-selftest", "version": "1"}}},
                   auth)
    check("initialize 返回 200", s == 200, b)
    try:
        info = json.loads(b)["result"]["serverInfo"]
        check("serverInfo.name = dust-hazard-judge",
              info.get("name") == "dust-hazard-judge", info)
    except Exception as e:
        check("initialize 报文可解析", False, e)
    sid = h.get("Mcp-Session-Id", "")
    headers = dict(auth)
    if sid:
        headers["Mcp-Session-Id"] = sid
        print("       session: " + sid)

    print("[3] 通知报文应返回 202")
    s, _, b = post(base, {"jsonrpc": "2.0", "method": "notifications/initialized"}, headers)
    check("notifications/initialized -> 202", s == 202, "%s %s" % (s, b[:80]))

    print("[4] 工具清单")
    s, _, b = post(base, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers)
    names = []
    try:
        names = [t["name"] for t in json.loads(b)["result"]["tools"]]
    except Exception:
        pass
    expect = {"judge", "list_clauses", "clause_detail", "clause_search", "clause_check", "render_doc"}
    check("六个工具齐全", set(names) == expect, names)

    print("[5] 工具调用")
    # 5.1 构成
    s, d, b = call(base, "judge", {"industry": "粉尘涉爆",
                                   "facts": {"dust.cleaning_not_implemented": True}}, headers)
    sc = (d or {}).get("result", {}).get("structuredContent") or {}
    check("judge 积尘严重 -> HIT", sc.get("verdict") == "HIT", b)
    if sc.get("render"):
        print("       " + sc["render"].replace("\n", "\n       ")[:220])

    # 5.2 不构成
    s, d, b = call(base, "judge", {"industry": "粉尘涉爆",
                                   "facts": {"dust_collector.type": "wet",
                                             "dust_collector.dust_kind": "wood"}}, headers)
    sc = (d or {}).get("result", {}).get("structuredContent") or {}
    check("judge 湿式除尘 -> 非 HIT", sc.get("verdict") in ("MISS", "PENDING"), sc.get("verdict"))

    # 5.3 待核实 + 追问
    s, d, b = call(base, "judge", {"industry": "粉尘涉爆",
                                   "facts": {"dust_collector.dust_kind": "wood"}}, headers)
    sc = (d or {}).get("result", {}).get("structuredContent") or {}
    check("judge 信息不足 -> PENDING", sc.get("verdict") == "PENDING", sc.get("verdict"))
    check("ask_more 是整数", isinstance(sc.get("ask_more"), int), type(sc.get("ask_more")))

    # 5.4 条款详情
    s, d, b = call(base, "clause_detail", {"clause_id": "DUST-10-006"}, headers)
    sc = (d or {}).get("result", {}).get("structuredContent") or {}
    check("clause_detail 命中 DUST-10-006", sc.get("found") is True, b)
    check("带条文原文", bool((sc.get("source") or {}).get("original")))

    # 5.5 出文书
    s, d, b = call(base, "render_doc", {
        "doc_type": "现场检查记录", "industry": "粉尘涉爆",
        "facts": {"dust.cleaning_not_implemented": True},
        "meta": {"企业名称": "某木质家具厂", "检查时间": "2026-11-25",
                 "检查地点": "一号车间", "执法人员": "张三、李四", "被检查人": "王五"}}, headers)
    sc = (d or {}).get("result", {}).get("structuredContent") or {}
    check("render_doc 生成成功", sc.get("ok") is True, sc.get("message"))
    check("含草稿水印与签名位",
          "草稿" in (sc.get("draft") or "") and "签名" in (sc.get("draft") or ""))

    print("\n通过 %d 项，失败 %d 项" % (len(OK), len(FAIL)))
    if FAIL:
        print("失败项：" + "、".join(FAIL))
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
