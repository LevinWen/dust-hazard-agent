# -*- coding: utf-8 -*-
"""
判定引擎的工具层（B1 + B2 交付物的核心）
=========================================

把 engine/dust_judge.py 里的确定性引擎包成 6 个对外工具，供 MCP 服务、
AgentArts 插件、评测脚本、Demo 前端共用同一份实现。

红线（分工书）：
- 判定逻辑与条款内容一个字都不改，全部转调 engine.dust_judge
- 给用户看的文本一律来自引擎返回的 render，本层不生成自然语言结论
- 文书只做「模板 + 要素填充」，不拼 HTML，不让模型写正文

六个工具：
    judge           判定（事实 -> 三态结论）
    list_clauses    列条款
    clause_detail   条款详情
    clause_search   条款检索（现象文本 -> 候选条款）
    clause_check    条款校验（结构 + 时效）
    render_doc      出文书（模板渲染 + 要素校验）
"""

from __future__ import annotations

import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

try:  # 作为包的一部分导入（pip install 后走这条）
    from .engine import dust_judge as engine  # noqa: E402
except ImportError:  # 直接运行本文件时的兜底
    sys.path.insert(0, os.path.join(_HERE, "engine"))
    import dust_judge as engine  # noqa: E402

ENGINE_VERSION = "2026-11-23 / flow e95493dc / ver 1794547987922"

# ---------------------------------------------------------------------------
# 字段字典：来自《平台配置说明.txt》第四节「大模型节点抽取提示词」的 12 个键
# 用途：校验 facts 合法性、给追问字段写法说明、做文书要素核对
# ---------------------------------------------------------------------------
FACT_FIELDS = {
    "dust_collector.type": {
        "type": "enum", "values": ["dry", "wet", "none"],
        "desc": "除尘系统类型：干式 / 湿式 / 没装",
    },
    "dust_collector.dust_kind": {
        "type": "enum", "values": ["metal", "wood", "other"],
        "desc": "粉尘种类：金属 / 木质 / 其他",
    },
    "dust_area.layout_violation": {
        "type": "bool", "desc": "场所布局违规（设在非框架结构多层建筑内、或内设人员聚集场所）",
    },
    "dust_collector.mixed_shared": {
        "type": "bool", "desc": "不同类别粉尘/不同防火分区共用一套除尘系统或互联互通",
    },
    "dust_collector.control_measures": {
        "type": "array", "values": ["vent", "inerting", "suppression"],
        "desc": "已装的爆炸防控措施：vent 泄爆 / inerting 惰化 / suppression 抑爆；一种都没装给 []",
    },
    "dust_collector.positive_pressure": {
        "type": "bool", "desc": "采用正压除尘方式",
    },
    "dust_collector.gravity_or_tunnel_duct": {
        "type": "bool", "desc": "采用重力沉降室除尘，或用干式巷道式构筑物作除尘风道",
    },
    "dust_collector.no_ash_discharge": {
        "type": "bool", "desc": "未设置锁气卸灰装置",
    },
    "dust_area.electrical_not_proof": {
        "type": "bool", "desc": "粉尘爆炸危险场所电气设备不符合防爆要求",
    },
    "process.no_debris_removal": {
        "type": "bool", "desc": "未落实粉尘清扫制度/未及时清理粉尘（作业现场积尘）",
    },
    "dust_area.no_hydrogen_or_damp_proof": {
        "type": "bool", "desc": "未采取防氢气积聚或防潮措施（金属粉尘湿式除尘场景）",
    },
    "dust.cleaning_not_implemented": {
        "type": "bool", "desc": "未落实粉尘清理制度，造成作业现场积尘严重",
    },
}

_STAGE_LABEL = {
    "need_industry": "待确认领域",
    "describe": "待描述现场",
    "ask": "待补充信息",
    "hit": "构成重大隐患",
    "miss": "未发现",
    "na": "不适用",
    "error": "入参错误",
}

_VERDICT_LABEL = {
    "HIT": "构成重大事故隐患",
    "MISS": "不构成",
    "PENDING": "待核实",
    "NA": "不适用",
    "ERROR": "错误",
}


# ---------------------------------------------------------------------------
# 工具 1：judge
# ---------------------------------------------------------------------------
def judge(facts=None, industry=None, clause_ids=None, payload=None) -> dict:
    """判定。直接转调引擎 main()，本函数不参与任何判定。"""
    args = {}
    if payload is not None:
        args["payload"] = payload
    if facts is not None:
        args["facts"] = facts
    if industry is not None:
        args["industry"] = industry
    if clause_ids is not None:
        args["clause_ids"] = clause_ids

    result = engine.main(args)

    result["verdict_label"] = _VERDICT_LABEL.get(result.get("verdict"), "")
    result["stage_label"] = _STAGE_LABEL.get(result.get("stage"), "")
    result["engine_version"] = ENGINE_VERSION
    result["facts_warnings"] = validate_facts(facts) if isinstance(facts, dict) else []
    return result


def validate_facts(facts) -> list:
    """校验 facts 的键名与取值，返回告警列表（不阻断判定）。"""
    if not isinstance(facts, dict):
        return [{"level": "error", "message": "facts 必须是 JSON 对象"}]
    out = []
    for k, v in facts.items():
        if k not in FACT_FIELDS:
            out.append({"level": "warn", "field": k,
                        "message": "未知字段，引擎会忽略；请核对字段字典"})
            continue
        spec = FACT_FIELDS[k]
        if spec["type"] == "bool" and not isinstance(v, bool):
            out.append({"level": "warn", "field": k,
                        "message": "该字段应为布尔值，收到 %r" % (v,)})
        elif spec["type"] == "enum" and v not in spec["values"]:
            out.append({"level": "warn", "field": k,
                        "message": "取值应为 %s 之一，收到 %r" % ("/".join(spec["values"]), v)})
        elif spec["type"] == "array":
            if not isinstance(v, list):
                out.append({"level": "warn", "field": k,
                            "message": "该字段应为数组，收到 %r" % (v,)})
            else:
                bad = [x for x in v if x not in spec["values"]]
                if bad:
                    out.append({"level": "warn", "field": k,
                                "message": "含非法取值 %r，合法值 %s"
                                           % (bad, "/".join(spec["values"]))})
    return out


# ---------------------------------------------------------------------------
# 工具 2：list_clauses
# ---------------------------------------------------------------------------
def _clause_fields(clause) -> list:
    fields = []
    for a in clause.get("applicability") or []:
        fields.append(a.get("field"))
    for it in (clause.get("conditions") or {}).get("items") or []:
        fields.append(it.get("field"))
    seen, out = set(), []
    for f in fields:
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def list_clauses(industry=None, include_text=False) -> dict:
    """列条款：某行业适用的条款清单（默认不含判定条件细节）。"""
    ind = engine._match_industry(
        [industry] if isinstance(industry, str) else (industry or [])
    )
    known = engine._known_industries()

    rows = []
    for c in engine.CLAUSES:
        if ind and not (set(c.get("industry") or []) & set(ind)):
            continue
        src = c.get("source") or {}
        row = {
            "clause_id": c.get("clause_id"),
            "article": src.get("article"),
            "hazard_type": c.get("hazard_type"),
            "severity": c.get("severity"),
            "status": src.get("status"),
            "effective_time": src.get("effective_time"),
            "fields": _clause_fields(c),
            "evidence_required": c.get("evidence_required") or [],
        }
        if include_text:
            row["original"] = src.get("original")
            row["disposal_ref"] = c.get("disposal_ref") or []
        rows.append(row)

    return {
        "industry": ind or known,
        "known_industries": known,
        "total": len(rows),
        "clauses": rows,
    }


# ---------------------------------------------------------------------------
# 工具 3：clause_detail
# ---------------------------------------------------------------------------
def clause_detail(clause_id) -> dict:
    """条款详情：原文、判定条件、证据要求、处置依据、追问问句。"""
    for c in engine.CLAUSES:
        if c.get("clause_id") == clause_id:
            src = c.get("source") or {}
            questions = []
            for it in (c.get("conditions") or {}).get("items") or []:
                questions.append({
                    "field": it.get("field"),
                    "op": it.get("op"),
                    "value": it.get("value"),
                    "question": it.get("question"),
                    "evidence": it.get("evidence"),
                })
            return {
                "found": True,
                "clause_id": clause_id,
                "source": src,
                "industry": c.get("industry") or [],
                "hazard_type": c.get("hazard_type"),
                "severity": c.get("severity"),
                "applicability": c.get("applicability") or [],
                "conditions": c.get("conditions") or {},
                "hit_when": c.get("hit_when", True),
                "evidence_required": c.get("evidence_required") or [],
                "disposal_ref": c.get("disposal_ref") or [],
                "fields": _clause_fields(c),
                "ask_rules": questions,
                "meta": c.get("meta") or {},
            }
    return {
        "found": False,
        "clause_id": clause_id,
        "message": "条款库中不存在该编号，请先用 list_clauses 或 clause_search 获取合法编号",
        "known_clause_ids": [c.get("clause_id") for c in engine.CLAUSES],
    }


# ---------------------------------------------------------------------------
# 工具 4：clause_search
# ---------------------------------------------------------------------------
# 现象词典：口语 -> 线索词。规则「词典优先、未命中就说未命中」，不硬套。
_PHENOMENA = [
    (("除尘器", "除尘系统", "风管", "吸尘"), "d", None),
    (("泄爆", "泄爆片", "泄压", "惰化", "抑爆", "防爆措施"), None, "dust_collector.control_measures"),
    (("积尘", "木屑", "灰", "清扫", "清理"), None, "dust.cleaning_not_implemented"),
    (("正压",), None, "dust_collector.positive_pressure"),
    (("沉降室", "地沟", "巷道", "风道"), None, "dust_collector.gravity_or_tunnel_duct"),
    (("卸灰", "锁气", "排灰"), None, "dust_collector.no_ash_discharge"),
    (("宿舍", "办公室", "会议室", "休息室", "多层", "框架结构"), None, "dust_area.layout_violation"),
    (("共用", "互联", "连通", "一套除尘"), None, "dust_collector.mixed_shared"),
    (("防爆", "电气", "电线", "开关", "照明"), None, "dust_area.electrical_not_proof"),
    (("氢气", "防潮", "潮湿", "湿式"), None, "dust_area.no_hydrogen_or_damp_proof"),
]


def clause_search(text, industry=None, top_k=3) -> dict:
    """条款检索：现象文本 -> 候选条款（带命中理由与缺失信息）。"""
    text = (text or "").strip()
    if not text:
        return {"matched": False, "message": "text 不能为空", "candidates": []}

    ind = engine._match_industry(
        [industry] if isinstance(industry, str) else (industry or [])
    )
    pool = [c for c in engine.CLAUSES
            if not ind or (set(c.get("industry") or []) & set(ind))]

    hinted_fields, hinted_clause_words = [], []
    for words, _, field in _PHENOMENA:
        if field and any(w in text for w in words):
            hinted_fields.append(field)
    for c in pool:
        if any(w in text for w in ("除尘", "风管")):
            pass

    scored = []
    for c in pool:
        src = c.get("source") or {}
        score, reasons = 0.0, []
        fields = _clause_fields(c)
        # 1) 词典给出的字段线索
        for f in fields:
            if f in hinted_fields:
                score += 3
                reasons.append("现象关键词指向判定字段 %s" % f)
        # 2) 条款原文与描述的字面重合
        hay = " ".join([
            str(src.get("original") or ""),
            str(src.get("article") or ""),
            " ".join(str(it.get("desc") or "") for it in
                     (c.get("conditions") or {}).get("items") or []),
        ])
        for w in set(re.findall(r"[\u4e00-\u9fa5]{2,4}", text)):
            if w in hay:
                score += 1
                reasons.append("与条款原文重合「%s」" % w)
        if score > 0:
            scored.append((score, c, reasons))

    scored.sort(key=lambda t: -t[0])
    top = scored[:max(1, int(top_k or 3))]

    if not top:
        return {
            "matched": False,
            "message": "未匹配到明确条款，建议按「除尘系统类型」「防控措施」「积尘清理」三类进一步核实，不要硬套条款",
            "candidates": [],
        }

    candidates = []
    for score, c, reasons in top:
        src = c.get("source") or {}
        candidates.append({
            "clause_id": c.get("clause_id"),
            "article": src.get("article"),
            "original": src.get("original"),
            "score": round(score, 2),
            "reasons": reasons[:4],
            "fields": _clause_fields(c),
            "missing_hint": "需补充字段：%s" % "、".join(_clause_fields(c)),
        })
    return {"matched": True, "candidates": candidates}


# ---------------------------------------------------------------------------
# 工具 5：clause_check
# ---------------------------------------------------------------------------
_REQUIRED_KEYS = ("clause_id", "source", "industry", "hazard_type",
                  "severity", "conditions", "hit_when")
_VALID_OPS = {"eq", "neq", "in", "not_in", "exists", "absent",
              "all_absent", "gt", "gte", "lt", "lte"}
_VALID_HAZARD = {"status", "absence", "behavior"}


def clause_check(clause=None, clause_id=None) -> dict:
    """条款校验：结构完整性 + 字段字典一致性 + 时效状态。"""
    if clause is None:
        if not clause_id:
            return {"ok": False, "errors": [{"message": "需要提供 clause 或 clause_id"}],
                    "warnings": []}
        found = clause_detail(clause_id)
        if not found.get("found"):
            return {"ok": False, "errors": [{"message": found.get("message")}],
                    "warnings": [], "known_clause_ids": found.get("known_clause_ids")}
        clause = found
        clause = {k: v for k, v in clause.items() if k not in ("found", "fields", "ask_rules")}

    errors, warnings = [], []

    for k in _REQUIRED_KEYS:
        if k not in clause:
            errors.append({"field": k, "message": "缺少必填字段"})

    src = clause.get("source") or {}
    for k in ("standard", "decree", "article", "original", "effective_time", "status"):
        if not src.get(k):
            errors.append({"field": "source." + k, "message": "来源字段缺失（判定依据无法溯源）"})
    if src.get("status") not in (None, "active"):
        warnings.append({"field": "source.status",
                         "message": "条款状态为 %r，判定时应被时效过滤" % (src.get("status"),)})
    if not src.get("supersedes"):
        warnings.append({"field": "source.supersedes",
                         "message": "未标注替代关系；建议注明被本条款替代的旧文件，便于从旧兼从轻"})

    if clause.get("hazard_type") not in (None, *_VALID_HAZARD):
        errors.append({"field": "hazard_type",
                       "message": "取值应为 %s 之一" % "/".join(sorted(_VALID_HAZARD))})

    cond = clause.get("conditions") or {}
    items = cond.get("items") or []
    if not items:
        errors.append({"field": "conditions.items", "message": "判定条件为空，条款不可执行"})
    if cond.get("logic") not in (None, "all", "any"):
        errors.append({"field": "conditions.logic", "message": "logic 只能是 all 或 any"})

    for it in items:
        fid = it.get("id")
        if not it.get("field"):
            errors.append({"field": "conditions.%s.field" % fid, "message": "缺少判定字段"})
        elif it["field"] not in FACT_FIELDS:
            errors.append({"field": it["field"],
                           "message": "字段不在工厂字段字典内，抽取节点永远填不出这个键"})
        else:
            spec = FACT_FIELDS[it["field"]]
            v = it.get("value")
            if spec["type"] == "bool" and not isinstance(v, bool):
                warnings.append({"field": it["field"],
                                 "message": "条件值与字段类型不一致：字典是布尔，条款给的是 %r" % (v,)})
            if spec["type"] == "enum" and v not in spec["values"]:
                warnings.append({"field": it["field"],
                                 "message": "条件值 %r 不在字典取值 %s 内" % (v, "/".join(spec["values"]))})
        if it.get("op") not in _VALID_OPS:
            errors.append({"field": "conditions.%s.op" % fid,
                           "message": "不支持的操作符 %r，引擎会返回 UNKNOWN" % (it.get("op"),)})
        if not it.get("evidence"):
            warnings.append({"field": "conditions.%s.evidence" % fid,
                             "message": "未写认定该条件需要什么证据"})
        if not it.get("question"):
            warnings.append({"field": "conditions.%s.question" % fid,
                             "message": "未写追问问句，命中 PENDING 时无法向执法人员提问"})

    cid = clause.get("clause_id")
    if cid and cid in [c.get("clause_id") for c in engine.CLAUSES]:
        warnings.append({"field": "clause_id",
                         "message": "条款库中已存在同编号条款，入库前需确认是替换还是新增版本"})

    return {"ok": not errors, "clause_id": cid, "errors": errors, "warnings": warnings}


# ---------------------------------------------------------------------------
# 工具 6：render_doc
# ---------------------------------------------------------------------------
_DRAFT_NOTICE = "【草稿】本文件由系统按规定模板生成，须经法定程序与审批后生效，不得直接作为正式文书使用。"

_DOC_TYPES = {
    "现场检查记录": {
        "required": ["企业名称", "检查时间", "检查地点", "执法人员", "被检查人"],
        "signature": ["执法人员签名：________________", "被检查人签名：________________"],
    },
    "责令限期整改指令书": {
        "required": ["企业名称", "检查时间", "执法人员", "整改期限"],
        "signature": ["执法人员签名：________________", "被检查人签收：________________"],
    },
}


def render_doc(doc_type, facts=None, industry=None, meta=None) -> dict:
    """出文书：模板 + 要素填充 + 完整性校验。要素不全就只出待补清单。"""
    meta = meta or {}
    if doc_type not in _DOC_TYPES:
        return {"ok": False,
                "message": "不支持的文书类型",
                "supported": list(_DOC_TYPES),
                "missing_fields": [], "draft": None}

    spec = _DOC_TYPES[doc_type]
    missing = [k for k in spec["required"] if not str(meta.get(k) or "").strip()]

    result = judge(facts=facts, industry=industry)
    if result.get("verdict") not in ("HIT", "MISS", "PENDING"):
        return {"ok": False,
                "message": "判定尚未得出结论（stage=%s），不生成文书" % result.get("stage"),
                "judge": {"verdict": result.get("verdict"), "stage": result.get("stage"),
                          "render": result.get("render")},
                "missing_fields": missing, "draft": None}

    if missing:
        # 分工书：关键要素缺失时拒绝生成完整文书，只给待补清单
        return {"ok": False,
                "message": "关键要素缺失，仅输出待补充清单",
                "missing_fields": missing,
                "judge": {"verdict": result["verdict"], "stage": result["stage"]},
                "checklist": ["请补充：%s" % k for k in missing],
                "draft": None}

    hits = result.get("hits") or []
    lines = [_DRAFT_NOTICE, "", "=" * 46, doc_type, "=" * 46, ""]
    lines.append("被检查单位：%s" % meta.get("企业名称"))
    lines.append("检查时间：%s" % meta.get("检查时间"))
    if meta.get("检查地点"):
        lines.append("检查地点：%s" % meta.get("检查地点"))
    lines.append("执法人员：%s" % meta.get("执法人员"))
    if meta.get("被检查人"):
        lines.append("被检查人：%s" % meta.get("被检查人"))
    lines.append("")
    lines.append("-" * 46)
    lines.append("一、判定结论")
    lines.append(result["render"])
    lines.append("")

    if hits:
        lines.append("二、认定依据（逐条）")
        for n, h in enumerate(hits, 1):
            lines.append("%d. %s" % (n, h.get("basis")))
            lines.append("   原文：%s" % h.get("original", ""))
            ev = h.get("evidence_required") or []
            if ev:
                lines.append("   应附证据：%s" % "、".join(ev))
            disp = h.get("disposal_ref") or []
            if disp:
                lines.append("   处置依据：%s" % "、".join(disp))
        lines.append("")

        if doc_type == "责令限期整改指令书":
            lines.append("三、整改要求")
            lines.append("1. 立即停止使用不符合要求的设施设备；")
            lines.append("2. 按上述依据完成整改，整改期限：%s；" % meta.get("整改期限"))
            lines.append("3. 整改完成后报请复查，未整改或整改不合格的依法处理。")
            lines.append("")

    pend = result.get("pending") or []
    if pend:
        lines.append("%s、待核实事项" % ("三" if doc_type == "现场检查记录" else "四"))
        for p in pend:
            lines.append("- %s：%s" % (p.get("clause_id"), p.get("detail")))
        lines.append("")

    lines.append("-" * 46)
    lines.extend(spec["signature"])
    draft = "\n".join(lines)

    return {
        "ok": True,
        "doc_type": doc_type,
        "judge": {"verdict": result["verdict"], "stage": result["stage"],
                  "hits": [h.get("clause_id") for h in hits]},
        "missing_fields": [],
        "draft": draft,
        "checks": {
            "要素完整": True,
            "含草稿水印": _DRAFT_NOTICE in draft,
            "含签名位": all(s in draft for s in spec["signature"]),
        },
    }


# ---------------------------------------------------------------------------
# 工具注册表（MCP 与 HTTP 两种外壳共用）
# ---------------------------------------------------------------------------
TOOLS = {
    "judge": {
        "description": "判定现场情况是否构成粉尘涉爆重大事故隐患。输入结构化事实，"
                       "返回三态结论（构成/不构成/待核实）与给用户看的文本。"
                       "不传事实则返回追问或让执法人员描述现场。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "facts": {"type": "object",
                          "description": "现场事实。键必须取自字段字典（如 dust_collector.type），没确认的键不要出现"},
                "industry": {"type": ["string", "array"], "items": {"type": "string"},
                             "description": "领域，如「粉尘涉爆」，可传字符串或数组"},
                "clause_ids": {"type": "array", "items": {"type": "string"},
                               "description": "只判定指定条款（可选，调试用）"},
                "payload": {"type": "string",
                            "description": "上游大模型输出的原始 JSON 文本（可含 ```json 围栏）"},
            },
        },
        "handler": judge,
    },
    "list_clauses": {
        "description": "列出某领域适用的条款清单（编号、条文、判定字段、证据要求）。"
                       "不含判定条件细节，需要细节用 clause_detail。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "industry": {"type": "string", "description": "领域，如「粉尘涉爆」；不传则返回全部"},
                "include_text": {"type": "boolean", "default": False,
                                 "description": "是否一并返回条文原文与处置依据"},
            },
        },
        "handler": list_clauses,
    },
    "clause_detail": {
        "description": "查询单条条款的完整定义：条文原文、判定条件、认定所需证据、"
                       "处置依据、追问问句。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "clause_id": {"type": "string", "description": "条款编号，如 DUST-10-003"},
            },
            "required": ["clause_id"],
        },
        "handler": clause_detail,
    },
    "clause_search": {
        "description": "把执法人员的口语描述（如「除尘器没装泄爆片」）映射到候选条款。"
                       "词典优先；匹配不到会明确返回 matched=false，不会硬套。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "现场现象的口语描述"},
                "industry": {"type": "string", "description": "领域过滤（可选）"},
                "top_k": {"type": "integer", "default": 3, "description": "最多返回几条候选"},
            },
            "required": ["text"],
        },
        "handler": clause_search,
    },
    "clause_check": {
        "description": "校验条款定义是否可执行：必填结构、字段字典一致性、操作符白名单、"
                       "证据与问句是否齐备、时效状态。用于条款入库前的结构校验闸门。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "clause": {"type": "object", "description": "待校验的条款 JSON"},
                "clause_id": {"type": "string", "description": "或直接给条款编号，校验库内已有条款"},
            },
        },
        "handler": clause_check,
    },
    "render_doc": {
        "description": "按模板生成执法文书草稿并做要素完整性校验。要素不全时只返回待补清单，"
                       "不生成半成品文书。产出文本固定带「草稿」水印与签名位。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_type": {"type": "string", "enum": list(_DOC_TYPES),
                             "description": "文书类型"},
                "facts": {"type": "object", "description": "现场事实，同 judge"},
                "industry": {"type": "string", "description": "领域"},
                "meta": {"type": "object", "description": "文书要素：企业名称、检查时间、检查地点、执法人员、被检查人、整改期限"},
            },
            "required": ["doc_type"],
        },
        "handler": render_doc,
    },
}


def call_tool(name, arguments):
    """统一入口：按工具名分发。未知工具抛出 KeyError 由外壳转成协议错误。"""
    spec = TOOLS.get(name)
    if spec is None:
        raise KeyError("未知工具：%s；可用：%s" % (name, ", ".join(TOOLS)))
    args = arguments or {}
    if not isinstance(args, dict):
        raise TypeError("arguments 必须是 JSON 对象")
    return spec["handler"](**args)


def tools_manifest():
    """给 MCP tools/list 与 OpenAPI 生成用的清单（不含 handler）。"""
    return [{"name": n, "description": s["description"], "inputSchema": s["inputSchema"]}
            for n, s in TOOLS.items()]


if __name__ == "__main__":
    # 冒烟测试：跑《平台配置说明.txt》第八节的四个调试用例
    cases = [
        ("用例1 空输入", dict(payload={"industry": "", "facts": {}}), "need_industry"),
        ("用例2 说粉尘", dict(payload={"industry": "粉尘", "facts": {}}), "describe"),
        ("用例3 干式木粉尘无卸灰", dict(payload={
            "industry": "粉尘",
            "facts": {"dust_collector.type": "dry",
                      "dust_collector.dust_kind": "wood",
                      "dust_collector.control_measures": ["vent"],
                      "dust_collector.no_ash_discharge": True}}), "hit"),
        ("用例4 有限空间", dict(payload={"industry": "有限空间", "facts": {}}), "need_industry"),
    ]
    bad = 0
    for label, args, expect in cases:
        r = call_tool("judge", args)
        ok = r.get("stage") == expect
        bad += 0 if ok else 1
        print(("OK  " if ok else "FAIL") + " %-22s stage=%-14s verdict=%s"
              % (label, r.get("stage"), r.get("verdict")))
        print("     " + (r.get("render") or "").replace("\n", "\n     "))
    print("\n工具数：%d，冒烟用例失败：%d" % (len(TOOLS), bad))
    raise SystemExit(1 if bad else 0)
