# CHANGELOG（引擎同步记录）

## 2026-11-23 · 打包与平台调研

- 重构成标准可安装包 `dust_hazard_mcp/`，新增 `pyproject.toml`
  - `pip install .` 后得到两个命令：`dust-hazard-mcp`（MCP 服务）、`dust-hazard-http`（HTTP 外壳）
  - 根目录保留 `server.py` / `tools.py` / `http_server.py` 三个兼容入口，老命令照旧可用
  - 干净 venv 内 `pip install dist/*.whl` 验证通过，console script 端到端跑出正确判定
- 修复：Windows 管道/部分客户端在首行带 UTF-8 BOM 时 JSON-RPC 解析失败，改为先 `lstrip("\ufeff")`
  - 自测从 39 项增到 40 项（新增 BOM 回归）
- 平台调研结论（决定了接入路线）：
  - **MCP 服务支持 Stdio 类型**，平台提示「支持安装命令为 NPX、UVX 的 MCP」，表单只有 参数/环境变量/请求头
    → 平台自己执行安装命令，**不需要自备公网域名**；前提是包能发布到公开 registry（PyPI / npm）
  - 插件路线：`OpenAPI导入` 是**粘贴 JSON**，平台不访问你的 URL；但「插件URL」是必填的运行时地址，
    工具「调试成功即可使用」→ 创建可离线，使用仍需公网 HTTPS
  - 平台文档明确「自定义插件为 API 类型插件」，没有在平台上写代码的函数型插件入口
- 仓库：代码已推送到 GitHub（私有），见项目根 `README.md`

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
