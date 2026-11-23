# -*- coding: utf-8 -*-
# ============================================================================
# 来源声明（不可删）
# 本文件是 AgentArts 平台工作流「重大事故隐患」中「判断」代码节点的**逐字副本**。
# 导出方式：登录 AgentArts 控制台 -> 智能体管理 -> 工作流 -> 重大事故隐患
#          -> 双击「判断」节点 -> 复制代码编辑器内容
# 导出时间：2026-11-23
# 工作流 ID：e95493dc-e48f-44af-9122-7208f038bf1d
# 版本 ID：1794547987922
# 归属：判定逻辑与条款内容属人工智能专业组；本组只做工程封装，不改判定逻辑。
# 若引擎更新，请重新导出覆盖本文件，并在 CHANGELOG 记一笔。
# ============================================================================
import json

_UNKNOWN = object()

_UNKNOWN_WORDS = {
    "", "unknown", "null", "none", "n/a", "na", "unknown_value",
    "未知", "不清楚", "不确定", "不详", "未提及", "没有提到", "无法确定", "-",
}

_TRUE_WORDS = {"true", "yes", "y", "1", "是", "有", "存在", "已设置", "已建立"}
_FALSE_WORDS = {"false", "no", "n", "0", "否", "没有", "不存在", "无", "未设置", "未建立"}

CONTROL_KEYS = ("facts", "industry", "clause_ids", "stage", "payload")

INDUSTRY_ALIAS = {
    "粉尘涉爆": "粉尘涉爆",
    "涉爆粉尘": "粉尘涉爆",
    "粉尘爆炸": "粉尘涉爆",
    "可燃性粉尘": "粉尘涉爆",
    "粉尘": "粉尘涉爆",
}

_HAZARD_ORDER = {"status": 0, "absence": 1, "behavior": 2}

_MAX_ASK = 2

CLAUSES_JSON = r"""
[
  {
    "$schema": "./clause.schema.json",
    "schema_version": "1.1",
    "clause_id": "DUST-10-001",
    "source": {
      "standard": "工贸企业重大事故隐患判定标准",
      "decree": "应急管理部令第10号",
      "article": "第十一条 第（一）项",
      "original": "粉尘爆炸危险场所设置在非框架结构的多层建(构)筑物内，或者粉尘爆炸危险场所内设有员工宿舍、会议室、办公室、休息室等人员聚集场所的",
      "effective_time": "2023-05-15",
      "status": "active",
      "supersedes": "安监总管四〔2017〕129号 第四条 相应条款（已废止）"
    },
    "industry": [
      "粉尘涉爆"
    ],
    "hazard_type": "status",
    "severity": "major",
    "applicability": [],
    "conditions": {
      "logic": "all",
      "items": [
        {
          "id": "c1",
          "desc": "场所布局不符合要求",
          "field": "dust_area.layout_violation",
          "op": "eq",
          "value": true,
          "evidence": "现场照片、施工图纸、场所平面布置图",
          "question": "粉尘爆炸危险场所设在非框架结构的多层建(构)筑物内吗？场所内有没有员工宿舍、会议室、办公室、休息室等人员聚集场所？"
        }
      ]
    },
    "hit_when": true,
    "evidence_required": [
      "现场照片",
      "施工图纸或场所平面布置图"
    ],
    "disposal_ref": [
      "安全生产法-第41条",
      "安全生产法-第97条"
    ],
    "meta": {
      "created_by": "Chen Zeming",
      "created_at": "2026-11-18",
      "version": "0.2"
    }
  },
  {
    "$schema": "./clause.schema.json",
    "schema_version": "1.1",
    "clause_id": "DUST-10-002",
    "source": {
      "standard": "工贸企业重大事故隐患判定标准",
      "decree": "应急管理部令第10号",
      "article": "第十一条 第（二）项",
      "original": "不同类别的可燃性粉尘、可燃性粉尘与可燃气体等易加剧爆炸危险的介质共用一套除尘系统，或者不同建(构)筑物、不同防火分区共用一套除尘系统、除尘系统互联互通的",
      "effective_time": "2023-05-15",
      "status": "active",
      "supersedes": "安监总管四〔2017〕129号 第四条 相应条款（已废止）"
    },
    "industry": [
      "粉尘涉爆"
    ],
    "hazard_type": "status",
    "severity": "major",
    "applicability": [],
    "conditions": {
      "logic": "all",
      "items": [
        {
          "id": "c1",
          "desc": "除尘系统混用或互联互通",
          "field": "dust_collector.mixed_shared",
          "op": "eq",
          "value": true,
          "evidence": "除尘系统管路图、现场管路照片",
          "question": "不同类别的可燃性粉尘、可燃性粉尘与可燃气体等易加剧爆炸危险的介质，有没有共用一套除尘系统？不同建(构)筑物、不同防火分区有没有共用一套除尘系统，或者除尘系统互联互通？"
        }
      ]
    },
    "hit_when": true,
    "evidence_required": [
      "除尘系统管路图",
      "现场管路照片"
    ],
    "disposal_ref": [
      "安全生产法-第41条",
      "安全生产法-第97条"
    ],
    "meta": {
      "created_by": "Chen Zeming",
      "created_at": "2026-11-18",
      "version": "0.2"
    }
  },
  {
    "$schema": "./clause.schema.json",
    "schema_version": "1.1",
    "clause_id": "DUST-10-003",
    "source": {
      "standard": "工贸企业重大事故隐患判定标准",
      "decree": "应急管理部令第10号",
      "article": "第十一条 第（三）项",
      "original": "干式除尘系统未采取泄爆、惰化、抑爆等任一种爆炸防控措施的",
      "effective_time": "2023-05-15",
      "status": "active",
      "supersedes": "安监总管四〔2017〕129号 第四条 相应条款（已废止）"
    },
    "industry": [
      "粉尘涉爆"
    ],
    "hazard_type": "absence",
    "severity": "major",
    "applicability": [
      {
        "id": "a1",
        "desc": "存在干式除尘系统",
        "field": "dust_collector.type",
        "op": "eq",
        "value": "dry",
        "evidence": "设备铭牌、除尘系统设计文件",
        "question": "现场除尘系统是干式还是湿式？"
      }
    ],
    "conditions": {
      "logic": "all",
      "items": [
        {
          "id": "c1",
          "desc": "未采取任一种爆炸防控措施",
          "field": "dust_collector.control_measures",
          "op": "all_absent",
          "value": [
            "vent",
            "inerting",
            "suppression"
          ],
          "evidence": "现场查看、除尘系统设计文件、安全设施台账",
          "question": "干式除尘系统装了哪些爆炸防控措施？泄爆、惰化、抑爆等，有哪几种？"
        }
      ]
    },
    "hit_when": true,
    "evidence_required": [
      "除尘系统类型证明",
      "爆炸防控措施清单或现场照片"
    ],
    "disposal_ref": [
      "安全生产法-第41条",
      "安全生产法-第97条"
    ],
    "meta": {
      "created_by": "Chen Zeming",
      "created_at": "2026-11-18",
      "version": "0.2"
    }
  },
  {
    "$schema": "./clause.schema.json",
    "schema_version": "1.1",
    "clause_id": "DUST-10-004",
    "source": {
      "standard": "工贸企业重大事故隐患判定标准",
      "decree": "应急管理部令第10号",
      "article": "第十一条 第（四）项",
      "original": "铝镁等金属粉尘除尘系统采用正压除尘方式，或者其他可燃性粉尘除尘系统采用正压吹送粉尘时，未采取火花探测消除等防范点燃源措施的",
      "effective_time": "2023-05-15",
      "status": "active",
      "supersedes": "安监总管四〔2017〕129号 第四条 相应条款（已废止）"
    },
    "industry": [
      "粉尘涉爆"
    ],
    "hazard_type": "status",
    "severity": "major",
    "applicability": [],
    "conditions": {
      "logic": "all",
      "items": [
        {
          "id": "c1",
          "desc": "采用正压除尘且未防范点燃源",
          "field": "dust_collector.positive_pressure",
          "op": "eq",
          "value": true,
          "evidence": "现场照片（风机与除尘器相对位置）、除尘系统设计文件",
          "question": "铝镁等金属粉尘除尘系统用的是正压除尘方式吗？其他可燃性粉尘除尘系统采用正压吹送粉尘时，有没有采取火花探测消除等防范点燃源措施？"
        }
      ]
    },
    "hit_when": true,
    "evidence_required": [
      "现场照片（体现风机与除尘器位置）",
      "除尘系统设计文件"
    ],
    "disposal_ref": [
      "安全生产法-第41条",
      "安全生产法-第97条"
    ],
    "meta": {
      "created_by": "Chen Zeming",
      "created_at": "2026-11-18",
      "version": "0.2"
    }
  },
  {
    "$schema": "./clause.schema.json",
    "schema_version": "1.1",
    "clause_id": "DUST-10-005",
    "source": {
      "standard": "工贸企业重大事故隐患判定标准",
      "decree": "应急管理部令第10号",
      "article": "第十一条 第（五）项",
      "original": "除尘系统采用重力沉降室除尘，或者采用干式巷道式构筑物作为除尘风道的",
      "effective_time": "2023-05-15",
      "status": "active",
      "supersedes": "安监总管四〔2017〕129号 第四条 相应条款（已废止）"
    },
    "industry": [
      "粉尘涉爆"
    ],
    "hazard_type": "status",
    "severity": "major",
    "applicability": [],
    "conditions": {
      "logic": "all",
      "items": [
        {
          "id": "c1",
          "desc": "采用重力沉降室或巷道式风道",
          "field": "dust_collector.gravity_or_tunnel_duct",
          "op": "eq",
          "value": true,
          "evidence": "现场照片、除尘系统形式说明",
          "question": "除尘系统是不是用重力沉降室除尘，或者用干式巷道式构筑物作为除尘风道？"
        }
      ]
    },
    "hit_when": true,
    "evidence_required": [
      "现场照片（沉降室或风道）",
      "除尘系统形式说明"
    ],
    "disposal_ref": [
      "安全生产法-第41条",
      "安全生产法-第97条"
    ],
    "meta": {
      "created_by": "Chen Zeming",
      "created_at": "2026-11-18",
      "version": "0.2"
    }
  },
  {
    "$schema": "./clause.schema.json",
    "schema_version": "1.1",
    "clause_id": "DUST-10-006",
    "source": {
      "standard": "工贸企业重大事故隐患判定标准",
      "decree": "应急管理部令第10号",
      "article": "第十一条 第（六）项",
      "original": "铝镁等金属粉尘、木质粉尘的干式除尘系统未设置锁气卸灰装置的",
      "effective_time": "2023-05-15",
      "status": "active",
      "supersedes": "安监总管四〔2017〕129号 第四条 相应条款（已废止）"
    },
    "industry": [
      "粉尘涉爆"
    ],
    "hazard_type": "absence",
    "severity": "major",
    "applicability": [
      {
        "id": "a1",
        "desc": "属于铝镁等金属粉尘或木质粉尘",
        "field": "dust_collector.dust_kind",
        "op": "in",
        "value": [
          "metal",
          "wood"
        ],
        "evidence": "工艺资料、粉尘性质检测报告",
        "question": "这家企业产生的可燃性粉尘是铝镁等金属粉尘、木质粉尘，还是其他种类？"
      }
    ],
    "conditions": {
      "logic": "all",
      "items": [
        {
          "id": "c1",
          "desc": "未设置锁气卸灰装置",
          "field": "dust_collector.no_ash_discharge",
          "op": "eq",
          "value": true,
          "evidence": "现场照片（除尘器卸灰口）、设备图纸",
          "question": "铝镁等金属粉尘、木质粉尘的干式除尘系统，有没有设置锁气卸灰装置？"
        }
      ]
    },
    "hit_when": true,
    "evidence_required": [
      "现场照片（卸灰口）",
      "除尘设备图纸或铭牌"
    ],
    "disposal_ref": [
      "安全生产法-第41条",
      "安全生产法-第97条"
    ],
    "meta": {
      "created_by": "Chen Zeming",
      "created_at": "2026-11-18",
      "version": "0.2"
    }
  },
  {
    "$schema": "./clause.schema.json",
    "schema_version": "1.1",
    "clause_id": "DUST-10-007",
    "source": {
      "standard": "工贸企业重大事故隐患判定标准",
      "decree": "应急管理部令第10号",
      "article": "第十一条 第（七）项",
      "original": "除尘器、收尘仓等划分为20区的粉尘爆炸危险场所电气设备不符合防爆要求的",
      "effective_time": "2023-05-15",
      "status": "active",
      "supersedes": "安监总管四〔2017〕129号 第四条 相应条款（已废止）"
    },
    "industry": [
      "粉尘涉爆"
    ],
    "hazard_type": "behavior",
    "severity": "major",
    "applicability": [],
    "conditions": {
      "logic": "all",
      "items": [
        {
          "id": "c1",
          "desc": "20 区电气设备不符合防爆要求",
          "field": "dust_area.electrical_not_proof",
          "op": "eq",
          "value": true,
          "evidence": "设备铭牌防爆标志照片、防爆合格证、现场照片",
          "question": "除尘器、收尘仓等划分为 20 区的粉尘爆炸危险场所，电气设备是什么型？有没有防爆标志和防爆合格证？"
        }
      ]
    },
    "hit_when": true,
    "evidence_required": [
      "设备铭牌防爆标志照片",
      "防爆合格证",
      "现场照片"
    ],
    "disposal_ref": [
      "安全生产法-第41条",
      "安全生产法-第97条"
    ],
    "meta": {
      "created_by": "Chen Zeming",
      "created_at": "2026-11-18",
      "version": "0.2"
    }
  },
  {
    "$schema": "./clause.schema.json",
    "schema_version": "1.1",
    "clause_id": "DUST-10-008",
    "source": {
      "standard": "工贸企业重大事故隐患判定标准",
      "decree": "应急管理部令第10号",
      "article": "第十一条 第（八）项",
      "original": "粉碎、研磨、造粒等易产生机械点燃源的工艺设备前，未设置铁、石等杂物去除装置，或者木制品加工企业与砂光机连接的风管未设置火花探测消除装置的",
      "effective_time": "2023-05-15",
      "status": "active",
      "supersedes": "安监总管四〔2017〕129号 第四条 相应条款（已废止）"
    },
    "industry": [
      "粉尘涉爆"
    ],
    "hazard_type": "absence",
    "severity": "major",
    "applicability": [],
    "conditions": {
      "logic": "all",
      "items": [
        {
          "id": "c1",
          "desc": "未采取杂物去除或火花探测消除措施",
          "field": "process.no_debris_removal",
          "op": "eq",
          "value": true,
          "evidence": "现场照片（进料口除铁除石装置、砂光机风管探测装置）",
          "question": "粉碎、研磨、造粒等易产生机械点燃源的工艺设备前，有没有设置铁、石等杂物去除装置？木制品加工企业与砂光机连接的风管上，有没有设置火花探测消除装置？"
        }
      ]
    },
    "hit_when": true,
    "evidence_required": [
      "现场照片（进料口、风管探测装置）",
      "工艺流程图"
    ],
    "disposal_ref": [
      "安全生产法-第41条",
      "安全生产法-第97条"
    ],
    "meta": {
      "created_by": "Chen Zeming",
      "created_at": "2026-11-18",
      "version": "0.2"
    }
  },
  {
    "$schema": "./clause.schema.json",
    "schema_version": "1.1",
    "clause_id": "DUST-10-009",
    "source": {
      "standard": "工贸企业重大事故隐患判定标准",
      "decree": "应急管理部令第10号",
      "article": "第十一条 第（九）项",
      "original": "遇湿自燃金属粉尘收集、堆放、储存场所未采取通风等防止氢气积聚措施，或者干式收集、堆放、储存场所未采取防水、防潮措施的",
      "effective_time": "2023-05-15",
      "status": "active",
      "supersedes": "安监总管四〔2017〕129号 第四条 相应条款（已废止）"
    },
    "industry": [
      "粉尘涉爆"
    ],
    "hazard_type": "absence",
    "severity": "major",
    "applicability": [
      {
        "id": "a1",
        "desc": "属于遇湿自燃金属粉尘（铝镁等）",
        "field": "dust_collector.dust_kind",
        "op": "in",
        "value": [
          "metal"
        ],
        "evidence": "工艺资料、粉尘性质检测报告",
        "question": "这家企业产生的可燃性粉尘是铝镁等金属粉尘、木质粉尘，还是其他种类？"
      }
    ],
    "conditions": {
      "logic": "all",
      "items": [
        {
          "id": "c1",
          "desc": "未防止氢气积聚或未防水防潮",
          "field": "dust_area.no_hydrogen_or_damp_proof",
          "op": "eq",
          "value": true,
          "evidence": "现场照片（通风设施、防潮措施）、场所平面图",
          "question": "遇湿自燃金属粉尘收集、堆放、储存场所，有没有采取通风等防止氢气积聚措施？干式收集、堆放、储存场所，有没有采取防水、防潮措施？"
        }
      ]
    },
    "hit_when": true,
    "evidence_required": [
      "现场照片（通风与防潮设施）",
      "粉尘种类证明"
    ],
    "disposal_ref": [
      "安全生产法-第41条",
      "安全生产法-第97条"
    ],
    "meta": {
      "created_by": "Chen Zeming",
      "created_at": "2026-11-18",
      "version": "0.2"
    }
  },
  {
    "$schema": "./clause.schema.json",
    "schema_version": "1.1",
    "clause_id": "DUST-10-010",
    "source": {
      "standard": "工贸企业重大事故隐患判定标准",
      "decree": "应急管理部令第10号",
      "article": "第十一条 第（十）项",
      "original": "未落实粉尘清理制度，造成作业现场积尘严重的",
      "effective_time": "2023-05-15",
      "status": "active",
      "supersedes": "安监总管四〔2017〕129号 第四条 相应条款（已废止）"
    },
    "industry": [
      "粉尘涉爆"
    ],
    "hazard_type": "status",
    "severity": "major",
    "applicability": [],
    "conditions": {
      "logic": "all",
      "items": [
        {
          "id": "c1",
          "desc": "未落实粉尘清理制度、积尘严重",
          "field": "dust.cleaning_not_implemented",
          "op": "eq",
          "value": true,
          "evidence": "现场照片（积尘部位）、粉尘清理制度、清理记录",
          "question": "粉尘清理制度有没有落实？作业现场积尘严重吗？"
        }
      ]
    },
    "hit_when": true,
    "evidence_required": [
      "现场照片（积尘部位）",
      "粉尘清理制度",
      "清理记录"
    ],
    "disposal_ref": [
      "安全生产法-第41条",
      "安全生产法-第97条"
    ],
    "meta": {
      "created_by": "Chen Zeming",
      "created_at": "2026-11-18",
      "version": "0.2"
    }
  }
]
"""

CLAUSES = json.loads(CLAUSES_JSON)

def _read(facts, path):
    if path not in facts:
        return _UNKNOWN
    v = facts[path]
    if v is None:
        return _UNKNOWN
    if isinstance(v, str) and v.strip().lower() in _UNKNOWN_WORDS:
        return _UNKNOWN
    return v

def _coerce(val, target):
    if isinstance(target, bool) and isinstance(val, str):
        s = val.strip().lower()
        if s in _TRUE_WORDS:
            return True
        if s in _FALSE_WORDS:
            return False
        return _UNKNOWN
    if isinstance(target, (int, float)) and not isinstance(target, bool) and isinstance(val, str):
        try:
            f = float(val.strip())
            return int(f) if isinstance(target, int) else f
        except ValueError:
            return _UNKNOWN
    return val

def _eval_cond(item, facts):
    val = _read(facts, item["field"])
    if val is _UNKNOWN:
        return "UNKNOWN"

    op = item["op"]
    target = item.get("value")
    val = _coerce(val, target)
    if val is _UNKNOWN:
        return "UNKNOWN"

    if op == "eq":
        return "TRUE" if val == target else "FALSE"
    if op == "neq":
        return "TRUE" if val != target else "FALSE"
    if op == "in":
        return "TRUE" if val in target else "FALSE"
    if op == "not_in":
        return "TRUE" if val not in target else "FALSE"
    if op == "exists":
        return "TRUE"
    if op == "absent":
        return "FALSE"
    if op == "all_absent":
        if isinstance(val, str):
            val = [val]
        try:
            return "TRUE" if not (set(val) & set(target)) else "FALSE"
        except TypeError:
            return "UNKNOWN"
    if op == "gt":
        return "TRUE" if val > target else "FALSE"
    if op == "gte":
        return "TRUE" if val >= target else "FALSE"
    if op == "lt":
        return "TRUE" if val < target else "FALSE"
    if op == "lte":
        return "TRUE" if val <= target else "FALSE"
    return "UNKNOWN"

def _judge_one(clause, facts):
    cid = clause.get("clause_id", "?")
    src = clause.get("source") or {}
    basis = "%s %s（%s）" % (src.get("standard", ""), src.get("article", ""),
                            src.get("decree", ""))

    for a in clause.get("applicability") or []:
        r = _eval_cond(a, facts)
        if r == "FALSE":
            return {"clause_id": cid, "verdict": "NA", "detail": "不适用本条款",
                    "basis": basis, "need_ask": []}
        if r == "UNKNOWN":
            return {"clause_id": cid, "verdict": "PENDING", "detail": "前置条件待确认",
                    "basis": basis, "need_ask": [{"field": a["field"],
                                                  "question": a.get("question", a["field"])}]}

    items = (clause.get("conditions") or {}).get("items") or []
    results = [(it["id"], it, _eval_cond(it, facts)) for it in items]
    truths = [r for _, _, r in results]

    logic = (clause.get("conditions") or {}).get("logic", "all")
    if logic == "all":
        if "FALSE" in truths:
            combined = "FALSE"
        elif all(t == "TRUE" for t in truths):
            combined = "TRUE"
        else:
            combined = "UNKNOWN"
    else:
        if "TRUE" in truths:
            combined = "TRUE"
        elif truths and all(t == "FALSE" for t in truths):
            combined = "FALSE"
        else:
            combined = "UNKNOWN"

    if combined == "UNKNOWN":
        ask = [{"field": it["field"], "question": it.get("question", it["field"])}
               for _, it, r in results if r == "UNKNOWN"]
        return {"clause_id": cid, "verdict": "PENDING",
                "detail": "信息不足: %s" % ",".join(x[0] for x in results if x[2] == "UNKNOWN"),
                "basis": basis, "need_ask": ask}

    hit = (combined == "TRUE") == bool(clause.get("hit_when", True))
    return {
        "clause_id": cid,
        "verdict": "HIT" if hit else "MISS",
        "detail": "命中条件" if hit else "条件不完全成立",
        "basis": basis,
        "severity": clause.get("severity", "major"),
        "original": src.get("original", ""),
        "evidence_required": clause.get("evidence_required", []),
        "disposal_ref": clause.get("disposal_ref", []),
        "need_ask": [],
    }

def _known_industries():
    out = []
    for c in CLAUSES:
        for i in c.get("industry") or []:
            if i not in out:
                out.append(i)
    return out


def _match_industry(industry):
    got = []
    for s in industry or []:
        s = str(s).strip()
        if not s:
            continue
        hit = None
        for k, v in INDUSTRY_ALIAS.items():
            if k in s:
                hit = v
                break
        got.append(hit or s)
    return got


def judge(facts, industry=None, clause_ids=None):
    ind = _match_industry(industry)
    names = "、".join(_known_industries()) or "（条款库为空）"

    if not ind and not clause_ids:
        return {"verdict": "PENDING", "stage": "need_industry",
                "hits": [], "pending": [], "need_ask": [],
                "ask_batch": [], "ask_more": 0, "checked": 0,
                "render": "本次检查哪个领域？目前支持：%s。" % names}

    pool = []
    for c in CLAUSES:
        if clause_ids and c.get("clause_id") not in clause_ids:
            continue
        if ind and not (set(c.get("industry") or []) & set(ind)):
            continue
        pool.append(c)

    if not pool:
        return {"verdict": "PENDING", "stage": "need_industry",
                "hits": [], "pending": [], "need_ask": [],
                "ask_batch": [], "ask_more": 0, "checked": 0,
                "render": "「%s」暂未接入，目前支持：%s。"
                          % ("、".join(ind) or "空", names)}

    if not facts:
        return {"verdict": "PENDING", "stage": "describe",
                "hits": [], "pending": [], "na": [], "need_ask": [],
                "ask_batch": [], "ask_more": 0, "checked": len(pool),
                "render": "现场发现哪些问题？哪些装置没装、哪些措施没落实、哪里不符合要求。"}

    results = [_judge_one(c, facts) for c in pool]
    hits = [r for r in results if r["verdict"] == "HIT"]
    pending = [r for r in results if r["verdict"] == "PENDING"]
    na = [r for r in results if r["verdict"] == "NA"]
    checked = len(pool) - len(na)

    if not checked:
        return {"verdict": "NA", "stage": "na",
                "hits": [], "pending": [], "na": na, "need_ask": [],
                "ask_batch": [], "ask_more": 0, "checked": 0,
                "render": "现场情况与粉尘涉爆重大隐患条款对不上，请确认粉尘类型和除尘方式。"}

    if hits:
        verdict = "HIT"
    elif pending:
        verdict = "PENDING"
    else:
        verdict = "MISS"

    cmap = dict((c.get("clause_id"), c) for c in pool)
    known = set()
    for k in facts:
        if "." in str(k):
            known.add(str(k).split(".")[0])

    ask, seen = [], set()
    for p in pending:
        hz = _HAZARD_ORDER.get((cmap.get(p["clause_id"]) or {}).get("hazard_type"), 9)
        for q in p["need_ask"]:
            if q["field"] in seen:
                continue
            seen.add(q["field"])
            pref = 0 if str(q["field"]).split(".")[0] in known else 1
            ask.append((pref, hz, q))
    ask.sort(key=lambda t: (t[0], t[1]))
    ask = [t[2] for t in ask]

    batch = ask[:_MAX_ASK]
    more = len(ask) - len(batch)

    if verdict == "HIT":
        lines = ["构成重大事故隐患。"]
        for h in hits:
            lines.append("依据：%s" % h["basis"])
            lines.append("原文：%s" % h["original"])
        render = "\n".join(lines)
        stage = "hit"
    elif verdict == "PENDING":
        if len(batch) == 1:
            render = batch[0]["question"]
        else:
            lines = ["还有两点需要确认："]
            for n, q in enumerate(batch, 1):
                lines.append("%d. %s" % (n, q["question"]))
            render = "\n".join(lines)
        stage = "ask"
    else:
        render = "根据现场情况，未发现构成重大事故隐患的情形。"
        stage = "miss"

    return {
        "verdict": verdict,
        "stage": stage,
        "hits": hits,
        "pending": pending,
        "na": na,
        "need_ask": ask,
        "ask_batch": batch,
        "ask_more": more,
        "checked": checked,
        "render": render,
    }

def _norm(v):
    if isinstance(v, str):
        t = v.strip()
        if t.startswith("```"):
            t = t.strip("`").strip()
            if t[:4].lower() == "json":
                t = t[4:].strip()
        if t[:1] in ("{", "[", '"'):
            try:
                return json.loads(t)
            except Exception:
                return v
    return v


def _clean(v):
    v = _norm(v)
    if isinstance(v, str):
        v = [v]
    if isinstance(v, (list, tuple)):
        out = [str(x).strip() for x in v if str(x).strip()]
        return out if out else None
    return None


def main(args: dict) -> dict:
    if not isinstance(args, dict):
        return {"verdict": "ERROR", "stage": "error", "render": "入参必须是 JSON 对象"}

    p = _norm(args.get("payload"))
    if not isinstance(p, dict):
        p = {}

    facts = _norm(args.get("facts"))
    if not isinstance(facts, dict):
        facts = _norm(p.get("facts"))
    if not isinstance(facts, dict):
        facts = dict((k, _norm(v)) for k, v in args.items()
                     if k not in CONTROL_KEYS)

    industry = _clean(args.get("industry")) or _clean(p.get("industry"))
    clause_ids = _clean(args.get("clause_ids")) or _clean(p.get("clause_ids"))

    result = judge(facts, industry, clause_ids)
    result["facts_used"] = sorted(facts.keys())
    return result

def _selftest():
    cases = []
    for c in CLAUSES:
        base = {}
        for a in c.get("applicability", []):
            v = a.get("value")
            base[a["field"]] = v[0] if isinstance(v, list) else v
        hit, miss = dict(base), dict(base)
        for it in c["conditions"]["items"]:
            op, fld, v = it["op"], it["field"], it.get("value")
            if op == "all_absent":
                hit[fld], miss[fld] = [], [v[0]]
            elif op in ("eq", "neq") and isinstance(v, bool):
                hit[fld], miss[fld] = v, not v
            else:
                hit[fld], miss[fld] = v, None
        cid = c["clause_id"]
        cases.append((cid + " 命中", hit, [cid], "HIT"))
        cases.append((cid + " 不构成", miss, [cid], "MISS"))
        cases.append((cid + " 缺信息", {}, [cid], "PENDING"))

    cases.append(("字符串 unknown 不得判 MISS",
                  {"dust_collector.positive_pressure": "unknown"},
                  ["DUST-10-004"], "PENDING"))
    cases.append(("字符串 false 应归一为否",
                  {"dust_collector.positive_pressure": "false"},
                  ["DUST-10-004"], "MISS"))
    cases.append(("装了泄爆一种即不构成",
                  {"dust_collector.type": "dry",
                   "dust_collector.control_measures": ["vent"]},
                  ["DUST-10-003"], "MISS"))
    cases.append(("缺除尘类型则本条待核实",
                  {"dust_collector.control_measures": []},
                  ["DUST-10-003"], "PENDING"))
    cases.append(("全部条款扫一遍、零采集",
                  {}, None, "PENDING"))
    cases.append(("facts 以 JSON 字符串传入",
                  json.dumps({"dust_collector.type": "dry",
                              "dust_collector.control_measures": []}),
                  ["DUST-10-003"], "HIT"))
    cases.append(("facts 字符串不是合法 JSON 时不崩",
                  "{not-json", None, "PENDING"))
    cases.append(("clause_ids 传单个字符串",
                  {"dust_area.layout_violation": True}, "DUST-10-001", "HIT"))
    cases.append(("clause_ids 空字符串视为不过滤",
                  {"dust_area.layout_violation": True}, "", "HIT"))
    cases.append(("clause_ids 空数组视为不过滤",
                  {"dust_area.layout_violation": True}, [], "HIT"))
    cases.append(("clause_ids 指定一条就只判一条",
                  {"dust_collector.type": "dry",
                   "dust_collector.control_measures": []},
                  ["DUST-10-003"], "HIT"))

    print("=" * 78)
    ok = 0
    fails = []
    for label, facts, ids, expect in cases:
        r = main({"facts": facts, "clause_ids": ids, "industry": "粉尘涉爆"})
        good = r["verdict"] == expect
        ok += good
        if not good:
            fails.append((label, expect, r["verdict"]))
            print("!! [%s] %s (期望 %s)" % (r["verdict"], label, expect))
    print("自测: %d/%d 通过" % (ok, len(cases)))
    for label, expect, got in fails:
        print("   失败: %s 期望 %s 实际 %s" % (label, expect, got))

    pcase = [
        ("payload 对象含领域与事实",
         {"payload": {"industry": "我们是做家具的木粉尘车间",
                      "facts": {"dust_collector.dust_kind": "wood",
                                "dust_collector.type": "dry",
                                "dust_collector.control_measures": []}}},
         "HIT"),
        ("payload 带围栏的 JSON 文本",
         {"payload": '```json\n{"industry": "粉尘企业", "facts": '
                     '{"dust_area.layout_violation": true}}\n```'},
         "HIT"),
        ("payload 只有领域",
         {"payload": {"industry": "铝镁粉尘车间"}}, "PENDING"),
    ]
    ok2 = 0
    for label, a, expect in pcase:
        r = main(a)
        good = r["verdict"] == expect
        ok2 += good
        print("   %s payload -> %-8s %s" % ("OK" if good else "!!", r["verdict"], label))

    print("-" * 78)
    for label, ind in (("粉尘", "粉尘"), ("铝镁粉尘企业", "我们是铝镁粉尘企业"),
                       ("粉尘涉爆", "粉尘涉爆"), ("木粉尘车间", "木粉尘车间")):
        r = main({"facts": {}, "industry": ind})
        print("领域「%s」-> %-12s 检查 %d 条" % (label, r["stage"], r["checked"]))
    for ind in ("有限空间", "", "危险化学品"):
        r = main({"facts": {}, "industry": ind})
        print("领域「%s」-> %-16s %s" % (ind or "(空)", r["stage"], r["render"][:34]))

    print("-" * 78)
    steps = [
        ("第 1 步 只说了领域", {}),
        ("第 2 步 描述：木粉尘、干式除尘、已装泄爆",
         {"dust_collector.dust_kind": "wood", "dust_collector.type": "dry",
          "dust_collector.control_measures": ["vent"]}),
        ("第 3 步 补齐其余情况",
         {"dust_collector.type": "dry", "dust_collector.dust_kind": "wood",
          "dust_area.layout_violation": False, "dust_collector.mixed_shared": False,
          "dust_collector.control_measures": ["vent"],
          "dust_collector.positive_pressure": False,
          "dust_collector.gravity_or_tunnel_duct": False,
          "dust_collector.no_ash_discharge": False,
          "dust_area.electrical_not_proof": False,
          "process.no_debris_removal": False,
          "dust_area.no_hydrogen_or_damp_proof": False,
          "dust.cleaning_not_implemented": False}),
    ]
    for label, f in steps:
        r = main({"facts": f, "industry": "木粉尘车间"})
        print("【%s】" % label)
        for line in r["render"].split("\n"):
            print("  " + line)
        print()
    return ok == len(cases) and ok2 == len(pcase)

if __name__ == "__main__":
    _selftest()
