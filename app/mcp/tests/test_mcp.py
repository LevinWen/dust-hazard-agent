# -*- coding: utf-8 -*-
"""
MCP 服务自测：真的把 server.py 当子进程拉起来，走完整 JSON-RPC 流程。
用法：python tests/test_mcp.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SERVER = os.path.join(ROOT, "server.py")

passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    print(("  OK   " if ok else "  FAIL ") + name + (("  <- " + detail) if detail and not ok else ""))
    return ok


class Client:
    def __init__(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        self.proc = subprocess.Popen(
            [sys.executable, "-u", SERVER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True, encoding="utf-8", bufsize=1,
        )
        self.seq = 0

    def send(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            self.seq += 1
            msg["id"] = self.seq
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read()
            raise RuntimeError("服务无响应，stderr:\n" + err)
        return json.loads(line)

    def call(self, name, arguments):
        resp = self.send("tools/call", {"name": name, "arguments": arguments})
        if "error" in resp:
            return {"__error__": resp["error"]}
        content = resp["result"]["content"][0]["text"]
        return json.loads(content)

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def main():
    c = Client()
    try:
        print("[1] 握手")
        r = c.send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "selftest", "version": "1.0"},
        })
        check("initialize 返回 result", "result" in r, json.dumps(r, ensure_ascii=False))
        info = r.get("result", {}).get("serverInfo", {})
        check("serverInfo.name 正确", info.get("name") == "dust-hazard-judge", str(info))
        check("声明 tools 能力", "tools" in r.get("result", {}).get("capabilities", {}))
        c.send("notifications/initialized", notify=True)

        print("[2] tools/list")
        r = c.send("tools/list")
        names = [t["name"] for t in r.get("result", {}).get("tools", [])]
        expect = {"judge", "list_clauses", "clause_detail",
                  "clause_search", "clause_check", "render_doc"}
        check("6 个工具齐全", set(names) == expect, str(names))
        for t in r.get("result", {}).get("tools", []):
            check("工具 %s 带 inputSchema" % t["name"], "inputSchema" in t)

        print("[3] ping")
        check("ping 返回空对象", c.send("ping").get("result") == {})

        print("[4] 四个调试用例（《平台配置说明.txt》第八节）")
        cases = [
            ("用例1 空输入", {"payload": {"industry": "", "facts": {}}},
             "need_industry", "本次检查哪个领域？目前支持：粉尘涉爆。"),
            ("用例2 说粉尘", {"payload": {"industry": "粉尘", "facts": {}}},
             "describe", "现场发现哪些问题？哪些装置没装、哪些措施没落实、哪里不符合要求。"),
            ("用例3 干式木粉尘无卸灰",
             {"payload": {"industry": "粉尘",
                          "facts": {"dust_collector.type": "dry",
                                    "dust_collector.dust_kind": "wood",
                                    "dust_collector.control_measures": ["vent"],
                                    "dust_collector.no_ash_discharge": True}}},
             "hit",
             "构成重大事故隐患。\n"
             "依据：工贸企业重大事故隐患判定标准 第十一条 第（六）项（应急管理部令第10号）\n"
             "原文：铝镁等金属粉尘、木质粉尘的干式除尘系统未设置锁气卸灰装置的"),
            ("用例4 有限空间", {"payload": {"industry": "有限空间", "facts": {}}},
             "need_industry", "「有限空间」暂未接入，目前支持：粉尘涉爆。"),
        ]
        for label, args, stage, render_expect in cases:
            r = c.call("judge", args)
            check(label + " stage=" + stage, r.get("stage") == stage, str(r.get("stage")))
            check(label + " render 一致", r.get("render") == render_expect,
                  repr(r.get("render")))

        print("[5] 三态判定")
        r = c.call("judge", {"facts": {"dust.cleaning_not_implemented": True},
                             "industry": "粉尘涉爆"})
        check("积尘严重 -> HIT", r.get("verdict") == "HIT", str(r.get("verdict")))
        check("命中数 >= 1", len(r.get("hits") or []) >= 1)
        r = c.call("judge", {"facts": {"dust_collector.type": "wet",
                                       "dust_collector.dust_kind": "wood"},
                             "industry": "粉尘涉爆"})
        check("湿式除尘 -> 不构成/PENDING", r.get("verdict") in ("MISS", "PENDING"),
              str(r.get("verdict")))
        r = c.call("judge", {"facts": {"dust_collector.dust_kind": "wood"},
                             "industry": "粉尘涉爆"})
        check("信息不足 -> PENDING", r.get("verdict") == "PENDING", str(r.get("verdict")))
        check("PENDING 带追问", bool(r.get("ask_batch")), str(r.get("ask_batch")))
        check("ask_more 是整数", isinstance(r.get("ask_more"), int), str(type(r.get("ask_more"))))

        print("[6] 条款工具")
        r = c.call("list_clauses", {"industry": "粉尘涉爆"})
        check("条款共 10 条", r.get("total") == 10, str(r.get("total")))
        cid = r["clauses"][0]["clause_id"]
        r2 = c.call("clause_detail", {"clause_id": cid})
        check("clause_detail 命中", r2.get("found") is True, cid)
        check("含条文原文", bool((r2.get("source") or {}).get("original")))
        r3 = c.call("clause_detail", {"clause_id": "NOT-EXIST"})
        check("不存在的编号 -> found=false", r3.get("found") is False)

        r4 = c.call("clause_search", {"text": "除尘器没装泄爆片，木屑积得厚"})
        check("clause_search 有候选", r4.get("matched") is True, str(r4))
        r5 = c.call("clause_search", {"text": "食堂卫生许可证过期了"})
        check("无关描述 -> matched=false（不硬套）", r5.get("matched") is False, str(r5))

        r6 = c.call("clause_check", {"clause_id": cid})
        check("库内条款校验 ok", r6.get("ok") is True, str(r6.get("errors")))
        bad = dict(cid=cid, source={}, industry=[], hazard_type="xxx",
                   severity="major", conditions={"logic": "all", "items": []}, hit_when=True)
        r7 = c.call("clause_check", {"clause": bad})
        check("残缺条款校验拦截", r7.get("ok") is False and len(r7.get("errors") or []) >= 3,
              str(r7.get("errors")))

        print("[7] 出文书")
        meta = {"企业名称": "某木质家具厂", "检查时间": "2026-11-23",
                "检查地点": "一号车间", "执法人员": "张三、李四", "被检查人": "王五",
                "整改期限": "2026-12-10"}
        r = c.call("render_doc", {"doc_type": "责令限期整改指令书",
                                  "industry": "粉尘涉爆",
                                  "facts": {"dust.cleaning_not_implemented": True},
                                  "meta": meta})
        check("文书生成成功", r.get("ok") is True, str(r.get("message")))
        check("含草稿水印", "草稿" in (r.get("draft") or ""))
        check("含签名位", "签名" in (r.get("draft") or ""))
        r2 = c.call("render_doc", {"doc_type": "责令限期整改指令书",
                                   "industry": "粉尘涉爆",
                                   "facts": {"dust.cleaning_not_implemented": True},
                                   "meta": {"企业名称": "某厂"}})
        check("要素缺失 -> 只给待补清单", r2.get("ok") is False and r2.get("missing_fields"),
              str(r2.get("missing_fields")))

        print("[8] 错误处理")
        r = c.send("tools/call", {"name": "no_such_tool", "arguments": {}})
        check("未知工具返回协议错误", "error" in r, str(r))
        r = c.send("no/such/method")
        check("未知方法返回 -32601", r.get("error", {}).get("code") == -32601, str(r))

        print("[9] 编码健壮性")
        # Windows 管道与部分客户端会在首行塞 UTF-8 BOM，不能因此解析失败
        c.proc.stdin.write("\ufeff" + json.dumps({"jsonrpc": "2.0", "id": 99, "method": "ping"}) + "\n")
        c.proc.stdin.flush()
        raw = c.proc.stdout.readline()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        check("首行带 BOM 仍能解析", isinstance(parsed, dict) and parsed.get("result") == {},
              raw.strip()[:120])

    finally:
        c.close()

    print("\n通过 %d 项，失败 %d 项" % (len(passed), len(failed)))
    if failed:
        print("失败项：" + "、".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
