# -*- coding: utf-8 -*-
"""
调用示例（HTTP 形态）：6 个工具各调一次，并把真实返回存成 sample_responses.json
============================================================================

先启动服务：
    python http_server.py --port 8080

再跑本脚本：
    python examples/call_http.py --base http://127.0.0.1:8080

这个脚本同时是「调用示例」和「真实返回样本」的生成器：
sample_responses.json 里的内容全部是跑出来的，不是手写的。
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sample_responses.json")


def post(base, name, payload, token=""):
    url = "%s/tools/%s" % (base.rstrip("/"), name)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


CASES = [
    # (工具名, 入参, 说明)
    ("judge", {"payload": {"industry": "", "facts": {}}},
     "用例1：什么都没说 -> 问领域"),
    ("judge", {"payload": {"industry": "粉尘", "facts": {}}},
     "用例2：说了粉尘 -> 让描述现场"),
    ("judge", {"facts": {"dust_collector.type": "dry",
                         "dust_collector.dust_kind": "wood",
                         "dust_collector.control_measures": ["vent"],
                         "dust_collector.no_ash_discharge": True},
               "industry": "粉尘涉爆"},
     "用例3：干式木粉尘除尘系统未装锁气卸灰 -> 构成（第十一条第（六）项）"),
    ("judge", {"facts": {"dust.cleaning_not_implemented": True},
               "industry": "粉尘涉爆"},
     "用例4：作业现场积尘严重 -> 构成（第十一条第（十）项）"),
    ("judge", {"facts": {"dust_collector.dust_kind": "wood"},
               "industry": "粉尘涉爆"},
     "用例5：只说了粉尘是木质 -> 信息不足，回待核实并追问"),
    ("judge", {"payload": {"industry": "有限空间", "facts": {}}},
     "用例6：未接入的领域 -> need_industry"),
    ("list_clauses", {"industry": "粉尘涉爆"}, "列出粉尘涉爆 10 条条款"),
    ("clause_detail", {"clause_id": "DUST-10-006"}, "查单条条款完整定义"),
    ("clause_search", {"text": "除尘器没装泄爆片，木屑积得厚", "top_k": 3},
     "口语描述 -> 候选条款"),
    ("clause_search", {"text": "食堂卫生许可证过期了"},
     "匹配不到任何条款 -> 明确说未命中，不硬套"),
    ("clause_check", {"clause_id": "DUST-10-006"}, "校验库内条款结构"),
    ("clause_check", {"clause": {"clause_id": "DUST-10-999", "source": {},
                                 "industry": [], "hazard_type": "bad",
                                 "conditions": {"logic": "all", "items": []}}},
     "校验残缺条款 -> 拦截报错"),
    ("render_doc", {"doc_type": "责令限期整改指令书",
                    "industry": "粉尘涉爆",
                    "facts": {"dust.cleaning_not_implemented": True},
                    "meta": {"企业名称": "某木质家具厂", "检查时间": "2026-11-23",
                             "检查地点": "一号生产车间", "执法人员": "张三、李四",
                             "被检查人": "王五", "整改期限": "2026-12-10"}},
     "出文书：要素齐全 -> 生成草稿（带水印与签名位）"),
    ("render_doc", {"doc_type": "现场检查记录", "industry": "粉尘涉爆",
                    "facts": {"dust.cleaning_not_implemented": True},
                    "meta": {"企业名称": "某木质家具厂"}},
     "出文书：要素缺失 -> 只给待补清单"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--token", default="")
    args = ap.parse_args()

    records = []
    for name, payload, note in CASES:
        try:
            result = post(args.base, name, payload, args.token)
            status = "OK"
        except urllib.error.HTTPError as e:
            result = json.loads(e.read().decode("utf-8"))
            status = "HTTP %d" % e.code
        records.append({"note": note, "tool": name,
                        "request": payload, "status": status, "response": result})
        print("[%s] %-14s %s" % (status, name, note))
        brief = result.get("render") if isinstance(result, dict) else None
        if brief:
            print("       render: " + brief.replace("\n", " / ")[:110])
        elif isinstance(result, dict) and result.get("total") is not None:
            print("       total: %s" % result["total"])
        elif isinstance(result, dict) and result.get("matched") is not None:
            print("       matched: %s" % result["matched"])
        elif isinstance(result, dict) and result.get("ok") is not None:
            print("       ok: %s" % result["ok"])

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"base": args.base,
                   "generated_at": "本地运行自动生成",
                   "count": len(records),
                   "records": records}, f, ensure_ascii=False, indent=2)
    print("\n已写入 %s（%d 条真实返回）" % (OUT, len(records)))


if __name__ == "__main__":
    main()
