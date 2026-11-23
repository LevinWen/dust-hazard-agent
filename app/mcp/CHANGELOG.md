# CHANGELOG（引擎同步记录）

## 2026-11-23 · 首次封装（工具集 v1.0.0）

- 从 AgentArts 工作流「重大事故隐患」的「判断」代码节点导出引擎，存为 `engine/dust_judge.py`
  - 工作流 ID `e95493dc-e48f-44af-9122-7208f038bf1d`，版本 ID `1794547987922`
  - 导出的文件顶部加了来源声明，**判定逻辑与条款内容未做任何修改**
  - 引擎自带自测：41/41 通过
- 平台上的旧插件「粉尘涉爆隐患判定」已按组内决定删除（废案），本工具集是重新实现
- 新增工具层 `tools.py`，六个工具：judge / list_clauses / clause_detail / clause_search / clause_check / render_doc
- 新增 MCP 服务 `server.py`（stdio，零依赖）
- 新增 HTTP 外壳 `http_server.py`（REST + JSON-RPC + OpenAPI 3.0）
- 新增自测 `tests/test_mcp.py`：39 项断言全绿
- 新增调用示例：`examples/call_local.py`、`examples/call_http.py`、`examples/sample_responses.json`（14 条真实返回）

### 待办
- [ ] 补 MCP SSE / Streamable HTTP 传输端点（视平台要求）
- [ ] `clause_search` 接向量兜底（设计书 3.5 的「词典优先、向量兜底」只实现了前半段）
- [ ] 文书模板扩到 3 类（缺整改复查意见书）
- [ ] 文书要素清单随契约文档定稿后同步
