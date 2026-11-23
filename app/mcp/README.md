# 判定工具集：MCP 服务 + HTTP 插件接口

> 分工书《三人分工与工作流功能规划》交付物第 2 项：**函数型插件或 MCP 服务，附接入说明与调用示例**。
> 覆盖表 5 的 B1（判定引擎插件化：判定 / 出文书 / 列条款）与 B2（自定义 MCP 服务：条款检索 / 条款详情 / 条款校验）。
> 负责人：计算机组。维护：2026-11-23。

---

## 一、这是什么

把工作流里那个「判断」代码节点的确定性引擎，从"只能被这一个工作流调用"，升级成**六个可独立调用的工具**：

| 工具 | 一句话 | 来源 |
|---|---|---|
| `judge` | 现场事实 → 构成 / 不构成 / 待核实 | B1 |
| `render_doc` | 按模板出执法文书草稿 + 要素校验 | B1 |
| `list_clauses` | 列某领域的条款清单 | B1 |
| `clause_search` | 执法人员的口语 → 候选条款 | B2 |
| `clause_detail` | 单条条款的完整定义 | B2 |
| `clause_check` | 条款结构校验（入库前的闸门） | B2 |

三个关键设计：

1. **判定逻辑零改动。** 全部转调 `engine/dust_judge.py`，那是平台工作流「判断」节点的逐字副本，本组只做封装。
2. **同一份实现、三种外壳。** MCP（stdio）、HTTP（八插件/OpenAPI）、进程内直调，三者的结论必然一致，因为底下是同一个 `tools.py`。
3. **零依赖。** 全部标准库，不用 `pip install`，答辩现场随便一台装了 Python 3.8+ 的机器就能跑。

---

## 二、目录结构

```
app/mcp/
├── pyproject.toml              打包配置（可 pip install，生成两个命令）
├── dust_hazard_mcp/            包本体
│   ├── __init__.py             对外只暴露 call_tool / TOOLS / tools_manifest
│   ├── tools.py                六个工具的实现 + 工具注册表（三种外壳共用）
│   ├── server.py               MCP 服务（stdio，按行分隔 JSON-RPC 2.0）
│   ├── http_server.py          HTTP 外壳（REST + JSON-RPC + OpenAPI）
│   └── engine/
│       └── dust_judge.py       平台「判断」节点逐字副本（含来源声明，勿改判定逻辑）
├── server.py / tools.py / http_server.py    兼容入口（让老命令照旧可用）
├── openapi.json                OpenAPI 3.0 描述，AgentArts 插件导入用这个
├── README.md                   本文件
├── CHANGELOG.md                引擎同步记录
├── examples/
│   ├── call_local.py           进程内直调示例
│   ├── call_http.py            HTTP 调用示例 + 真实返回生成器
│   ├── sample_responses.json   14 条真实返回（跑出来的，不是手写的）
│   └── mcp_client_config.json  MCP 客户端配置样例
└── tests/
    └── test_mcp.py             端到端自测，39 项断言
```

---

## 三、跑起来

### 方式 1：直接跑（不用装）

```bash
cd app/mcp

python -m dust_hazard_mcp      # 自检：列工具 + 六种状态机冒烟
python tests/test_mcp.py       # 端到端自测，期望「通过 39 项，失败 0 项」
python http_server.py --port 8080
```

### 方式 2：装成命令（推荐给平台与队友）

```bash
cd app/mcp
pip install .

dust-hazard-mcp                # MCP 服务（stdio）
dust-hazard-http --port 8080   # HTTP 外壳
```

装完得到两个命令：`dust-hazard-mcp`、`dust-hazard-http`。
零第三方依赖，`pip install` 只装自己。

Windows 下如果控制台中文乱码，先执行 `chcp 65001`，或设 `set PYTHONUTF8=1`。

---

## 四、六个工具的参数与返回

### 4.1 `judge` 判定

**入参**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `facts` | object | 否 | 现场事实。键必须取自字段字典，没确认的键**不要出现** |
| `industry` | string \| array | 否 | 领域，如 `粉尘涉爆` |
| `clause_ids` | array | 否 | 只判指定条款（调试用） |
| `payload` | string | 否 | 上游大模型输出的原始 JSON 文本，可带 ```` ```json ```` 围栏 |

`facts` 的 12 个合法键（字段字典，来自《平台配置说明.txt》第四节）：

| 键 | 类型 | 取值 / 含义 |
|---|---|---|
| `dust_collector.type` | enum | `dry` / `wet` / `none` |
| `dust_collector.dust_kind` | enum | `metal` / `wood` / `other` |
| `dust_area.layout_violation` | bool | 场所布局违规 |
| `dust_collector.mixed_shared` | bool | 混用或互联互通 |
| `dust_collector.control_measures` | array | `vent` 泄爆 / `inerting` 惰化 / `suppression` 抑爆；一种都没装给 `[]` |
| `dust_collector.positive_pressure` | bool | 正压除尘 |
| `dust_collector.gravity_or_tunnel_duct` | bool | 重力沉降室 / 干式巷道式风道 |
| `dust_collector.no_ash_discharge` | bool | 未设锁气卸灰装置 |
| `dust_area.electrical_not_proof` | bool | 电气设备不防爆 |
| `process.no_debris_removal` | bool | 未落实粉尘清扫 |
| `dust_area.no_hydrogen_or_damp_proof` | bool | 未防氢气积聚 / 未防潮 |
| `dust.cleaning_not_implemented` | bool | 未落实清理制度，积尘严重 |

**返回**（节选自 `examples/sample_responses.json`，真实返回）

```json
{
  "verdict": "HIT",
  "stage": "hit",
  "render": "构成重大事故隐患。\n依据：工贸企业重大事故隐患判定标准 第十一条 第（六）项（应急管理部令第10号）\n原文：铝镁等金属粉尘、木质粉尘的干式除尘系统未设置锁气卸灰装置的",
  "hits": [
    {
      "clause_id": "DUST-10-006",
      "basis": "工贸企业重大事故隐患判定标准 第十一条 第（六）项（应急管理部令第10号）",
      "original": "铝镁等金属粉尘、木质粉尘的干式除尘系统未设置锁气卸灰装置的",
      "evidence_required": ["现场照片（卸灰口）", "除尘设备图纸或铭牌"],
      "disposal_ref": ["安全生产法-第41条", "安全生产法-第97条"]
    }
  ],
  "pending": [],
  "na": [],
  "need_ask": [],
  "ask_batch": [],
  "ask_more": 0,
  "checked": 9,
  "facts_used": ["dust_collector.control_measures", "dust_collector.dust_kind",
                 "dust_collector.no_ash_discharge", "dust_collector.type"],
  "verdict_label": "构成重大事故隐患",
  "stage_label": "构成重大隐患",
  "engine_version": "2026-11-23 / flow e95493dc / ver 1794547987922",
  "facts_warnings": []
}
```

**这就是平台代码节点缺的那几个出参。** 工作流「判断」节点只配了 `verdict` / `render` / `stage` / `ask_more` 四个，
而引擎实际会返回 `hits` / `pending` / `na` / `need_ask` / `ask_batch` / `checked` / `facts_used`。
Demo 要做的「依据链展开」直接用这个工具就能拿到结构化条款明细，不必从 `render` 里正则抠。

`stage` 与 `verdict` 的对照：

| stage | verdict | 含义 | UI 表现 |
|---|---|---|---|
| `need_industry` | PENDING | 没识别出领域 / 领域未接入 | 问领域 |
| `describe` | PENDING | 有领域但没事实 | 让执法人员描述现场 |
| `ask` | PENDING | 信息不足，本轮追问 1~2 条 | 待核实 + 追问卡片 |
| `hit` | HIT | 命中重大隐患条款 | 红色 结论 + 依据链 |
| `miss` | MISS | 全部条款不成立 | 绿色 未发现 |
| `na` | NA | 条款全不适用 | 灰色 提示核对粉尘类型与除尘方式 |

### 4.2 `list_clauses` 列条款

| 参数 | 类型 | 说明 |
|---|---|---|
| `industry` | string | 领域，不传返回全部 |
| `include_text` | bool | 是否带条文原文与处置依据，默认 `false` |

返回：`{industry, known_industries, total, clauses[{clause_id, article, hazard_type, severity, status, effective_time, fields, evidence_required}]}`

### 4.3 `clause_detail` 条款详情

入参 `clause_id`（必填）。返回 `source`（含 `original` 原文、`decree` 文号、`effective_time`、`status`、`supersedes`）、
`conditions`、`evidence_required`、`disposal_ref`、`ask_rules`（每个判定条件的字段、操作符、`question`、`evidence`）。

条款不存在时返回 `found: false` 并附 `known_clause_ids`，不会编一个假编号。

### 4.4 `clause_search` 条款检索

| 参数 | 类型 | 说明 |
|---|---|---|
| `text` | string | 必填，口语描述 |
| `industry` | string | 领域过滤 |
| `top_k` | integer | 默认 3 |

返回 `matched` + `candidates[{clause_id, article, original, score, reasons, fields, missing_hint}]`。

**匹配不到时明确返回 `matched: false`**，并提示「建议按除尘系统类型 / 防控措施 / 积尘清理三类进一步核实，不要硬套条款」。
这是分工书里「允许未命中」的要求：查不到就说查不到，绝不硬套。

### 4.5 `clause_check` 条款校验

入参 `clause`（条款 JSON）或 `clause_id`（校验库内条款）。返回 `ok` + `errors[]` + `warnings[]`。

检查项：必填字段、来源可溯源（standard/decree/article/original/effective_time/status）、
`hazard_type` 取值、`conditions.items` 非空、`logic` 合法、
**判定字段是否在工厂字段字典内**（不在字典里的字段，抽取节点永远填不出来）、
操作符白名单、证据与问句是否齐备、时效状态、编号冲突。

这是「条款 JSON 结构校验」那道质量闸门的可执行版本，对应分工书表 9 第一道闸门。

### 4.6 `render_doc` 出文书

| 参数 | 类型 | 说明 |
|---|---|---|
| `doc_type` | string | `现场检查记录` / `责令限期整改指令书` |
| `facts` | object | 同 `judge` |
| `industry` | string | 领域 |
| `meta` | object | 文书要素：企业名称、检查时间、检查地点、执法人员、被检查人、整改期限 |

两条硬规则（分工书红线）：

- **要素不全不发文书**，只返回 `missing_fields` 待补清单，避免产出"看起来完整其实缺项"的文书
- 产出文本固定带「草稿，须经法定程序与审批后生效」水印与签名位，`checks` 里逐项自证

判定还没出结论时（`stage` 为 `need_industry` / `describe` / `ask`）也拒绝生成文书。

---

## 五、三种接入方式

### 方式 A：MCP（stdio）——推荐给 AgentArts 与本地客户端

```bash
python server.py
```

客户端配置见 `examples/mcp_client_config.json`：

```json
{
  "mcpServers": {
    "dust-hazard-judge": {
      "command": "python",
      "args": ["D:\\Files\\基层安全生产智能体\\app\\mcp\\server.py"],
      "env": { "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8" }
    }
  }
}
```

协议实现说明（自己实现的，方便排查）：

- 传输是 **stdin/stdout 上按行分隔的 JSON-RPC 2.0**，不是 LSP 的 `Content-Length` 头
- `stdout` 只输出协议报文，所有日志走 `stderr`
- 支持 `initialize` / `notifications/initialized` / `ping` / `tools/list` / `tools/call`；
  未知方法回 `-32601`，未知工具回 `-32602`，工具内部异常回 `isError: true` 但不中断会话

### 方式 B：HTTP + OpenAPI——AgentArts「插件」走这条

```bash
python http_server.py --port 8080
python http_server.py --port 8080 --token mytoken   # 开 Bearer 鉴权
```

| 接口 | 用途 |
|---|---|
| `GET /health` | 健康检查 |
| `GET /tools` | 工具清单 |
| `GET /openapi.json` | **OpenAPI 3.0 描述，插件导入填这个地址** |
| `POST /tools/{name}` | REST 直调，body 即入参 |
| `POST /rpc` | JSON-RPC 2.0，兼容 MCP 语义 |

已开 CORS，Demo 页面可以直接从浏览器调。

curl 一条：

```bash
curl -X POST http://127.0.0.1:8080/tools/judge \
  -H "Content-Type: application/json" \
  -d "{\"industry\":\"粉尘涉爆\",\"facts\":{\"dust.cleaning_not_implemented\":true}}"
```

### 方式 C：进程内直调——评测脚本用这个

```python
import sys; sys.path.insert(0, r"D:\Files\基层安全生产智能体\app\mcp")
import tools

r = tools.call_tool("judge", {
    "facts": {"dust.cleaning_not_implemented": True},
    "industry": "粉尘涉爆",
})
print(r["verdict"], r["render"])
```

装成包之后更简单：

```python
from dust_hazard_mcp import call_tool
r = call_tool("judge", {"facts": {"dust.cleaning_not_implemented": True},
                        "industry": "粉尘涉爆"})
```

完整示例见 `examples/call_local.py`。

---

## 六、在 AgentArts 上注册

### 路线 1：MCP 服务 → 选 **Stdio**（不需要公网域名）

「我的资产 → MCP → 创建MCP → 空白创建」，服务配置的类型有两个：

| 类型 | 平台提示 | 需要自己准备公网地址 |
|---|---|---|
| HTTP | 支持 SSE、Streamable HTTP 类的 MCP | 要（填 URL，云上服务来连） |
| **Stdio** | 支持安装命令为 **NPX、UVX** 的 MCP | **不要** |

Stdio 的字段只有三个：`参数`（多个用英文逗号分隔）、`环境变量（可选）`、`请求头（可选）`。
平台自己执行 `npx -y <包>` 或 `uvx <包>`，在你的机器之外拉起服务。

前提：**包必须能被公开 registry 安装到**（PyPI 或 npm）。本包已经可以用 `pip install .` 安装，
发布到 PyPI 后即可写成 `uvx dust-hazard-mcp`。

### 路线 2：插件（API 类型）

「我的资产 → 插件 → 创建插件」→ 基础信息：名称、描述 → `插件URL`（**必填**，运行时地址）→ 鉴权方式
→ 下一步创建工具时用「**OpenAPI导入**」：弹窗里是 JSON 编辑器，**粘贴** `openapi.json` 的内容即可，
平台不会去访问你的 URL。工具「调试成功即可使用」。

要点：**建插件可以离线，用插件不行。** 平台调工具时终究要打到填的那个 URL，所以要用起来仍然需要公网 HTTPS 地址。

### 路线 3：本地（答辩兜底）

本地 MCP 客户端（方式 A）或本地 HTTP 直调（方式 B），零外部依赖，断网也能演示。

> 结论：想让平台真正跑通，**Stdio MCP 是唯一不需要公网域名的路线**；插件路线需要域名，但创建阶段不需要。

---

## 七、验收自测

```bash
python tools.py                # 四个调试用例，期望全部 OK
python tests/test_mcp.py       # 39 项断言，期望"通过 39 项，失败 0 项"
```

`tests/test_mcp.py` 覆盖：握手与能力声明 → 六工具清单与 schema → 四个调试用例的 stage **与 render 全文逐字比对**
→ 三态判定（HIT / MISS / PENDING）→ 追问与 `ask_more` 类型 → 条款三工具 → 未命中不硬套
→ 残缺条款被拦截 → 文书生成与要素缺失拒发 → 未知工具/未知方法的错误码。

`examples/sample_responses.json` 里 14 条真实返回全部由 `examples/call_http.py` 跑出来，可直接贴进作品材料当证据。

---

## 八、已知限制（写清楚比藏着好）

| 限制 | 说明 | 影响 |
|---|---|---|
| 平台可达性 | 本地服务公网不可达、且是 HTTP 不是 HTTPS | 插件/MCP 注册要等部署或穿透，代码本身已就绪 |
| 仅 stdio 与 JSON-RPC over POST | 若平台只接受 MCP 的 SSE / Streamable HTTP 传输，需再加一个 SSE 端点 | 待确认平台要求后补，约 0.5 人日 |
| `clause_search` 无向量检索 | 现在是词典 + 字面重合打分。设计书 3.5 要求「词典优先、向量兜底」，向量部分未接 | 召回不如语义检索，但符合"不硬套"的取舍；接 embedding 后按同一接口替换 |
| 文书模板只有 2 类 | 现场检查记录、责令限期整改指令书 | 复查意见书等模板等要素清单定稿后补 |
| 文书要素清单待冻结 | 现在是企业名称/检查时间/检查地点/执法人员/被检查人/整改期限 | 契约文档定稿后同步，改的是 `_DOC_TYPES` 一处 |
| 领域只有粉尘涉爆 | 与引擎一致，其它领域走 `need_industry` | 扩领域由引擎侧加条款，工具层不用改 |

---

## 九、版本与来源

| 项 | 值 |
|---|---|
| 引擎来源 | AgentArts 工作流「重大事故隐患」→「判断」代码节点逐字副本 |
| 工作流 ID | `e95493dc-e48f-44af-9122-7208f038bf1d` |
| 版本 ID | `1794547987922` |
| 导出时间 | 2026-11-23 |
| 引擎自测 | 41/41 通过 |

引擎更新后：重新从平台导出，覆盖 `engine/dust_judge.py`（保留顶部来源声明），
跑 `python tests/test_mcp.py`，在 `CHANGELOG.md` 记一笔。**不要在本组这边改判定逻辑。**
