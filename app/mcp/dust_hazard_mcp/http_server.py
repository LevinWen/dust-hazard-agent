# -*- coding: utf-8 -*-
"""
HTTP 外壳（同一个工具层的第二种接入方式）
=========================================

为什么要有它：
AgentArts 的「插件」要求填写协议、域名、URL 并「导入并解析工具 URL」，
也就是需要一个 HTTP + OpenAPI 的接口。MCP 是 stdio 的，平台侧接不了；
所以同一套工具同时提供 HTTP 形态，注册插件时把 openapi.json 的地址填进去即可。

接口：
    GET  /health              健康检查
    GET  /tools               工具清单
    GET  /openapi.json        OpenAPI 3.0 描述（插件导入用这个）
    POST /tools/{name}        REST 直调，body 就是入参 JSON
    POST /rpc                 JSON-RPC 2.0（tools/list、tools/call，兼容 MCP 语义）

启动：
    python http_server.py --port 8080
    python http_server.py --port 8080 --token mytoken   # 开启 Bearer 鉴权

零依赖，只用标准库。
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:  # 包内导入
    from . import tools as tool_layer
except ImportError:  # 直接运行脚本时兜底
    import tools as tool_layer

_ARGS = None

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}


def _openapi(host):
    paths = {}
    for t in tool_layer.tools_manifest():
        paths["/tools/" + t["name"]] = {
            "post": {
                "operationId": t["name"],
                "summary": t["description"][:60],
                "description": t["description"],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": t["inputSchema"]}},
                },
                "responses": {
                    "200": {"description": "工具返回",
                            "content": {"application/json": {
                                "schema": {"type": "object",
                                           "description": "工具输出，见各工具说明"}}}}
                },
            }
        }
    return {
        "openapi": "3.0.1",
        "info": {
            "title": "粉尘涉爆重大事故隐患判定工具集",
            "version": "1.0.0",
            "description": "确定性判定引擎的 6 个工具：judge / list_clauses / "
                           "clause_detail / clause_search / clause_check / render_doc。"
                           "判定逻辑确定，同一输入永远得到同一结论。",
        },
        "servers": [{"url": host}],
        "paths": paths,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "DustHazardTools/1.0"

    # ---------------- 基础工具 ----------------
    def _send(self, code, payload, extra=None):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        raw = self.rfile.read(n).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError("请求体不是合法 JSON：%s" % e)

    def _auth_ok(self):
        if not _ARGS.token:
            return True
        got = self.headers.get("Authorization") or ""
        return got.strip() == "Bearer " + _ARGS.token

    def _base_url(self):
        host = self.headers.get("Host") or ("127.0.0.1:%d" % _ARGS.port)
        proto = self.headers.get("X-Forwarded-Proto") or "http"
        return "%s://%s" % (proto, host)

    def _rpc(self, msg):
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": msg.get("params", {}).get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "dust-hazard-judge", "version": "1.0.0"}}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"tools": tool_layer.tools_manifest()}}
        if method == "tools/call":
            params = msg.get("params") or {}
            try:
                result = tool_layer.call_tool(params.get("name"), params.get("arguments") or {})
            except Exception as e:
                return {"jsonrpc": "2.0", "id": mid,
                        "error": {"code": -32602, "message": str(e)}}
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text",
                             "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result, "isError": False}}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": mid, "result": {}}
        if mid is None:  # 通知类报文不需要响应
            return None
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": "不支持的方法：%s" % method}}

    # ---------------- 路由 ----------------
    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            return self._send(200, {"ok": True, "tools": len(tool_layer.TOOLS),
                                    "engine_version": tool_layer.ENGINE_VERSION})
        if path == "/tools":
            return self._send(200, {"tools": tool_layer.tools_manifest()})
        if path == "/openapi.json":
            return self._send(200, _openapi(self._base_url()))
        return self._send(404, {"error": "not found", "path": path})

    def do_POST(self):
        if not self._auth_ok():
            return self._send(401, {"error": "鉴权失败：需要 Authorization: Bearer <token>"})
        path = self.path.split("?")[0]
        try:
            body = self._body()
        except ValueError as e:
            return self._send(400, {"error": str(e)})

        if path in ("/rpc", "/mcp"):
            # /rpc 是宽松的 JSON-RPC；/mcp 额外实现 MCP Streamable HTTP 的必要细节：
            #   - 通知（无 id）返回 202 且无响应体
            #   - initialize 时下发 Mcp-Session-Id，后续请求若带上则原样回显
            sid = self.headers.get("Mcp-Session-Id") or ""
            if isinstance(body, list):
                payload = [self._rpc(m) for m in body]
                return self._send(200, payload, {"Mcp-Session-Id": sid} if sid else None)

            resp = self._rpc(body)
            if resp is None:
                extra = {"Mcp-Session-Id": sid or uuid.uuid4().hex}
                return self._send(202, {}, extra)

            extra = None
            if sid:
                extra = {"Mcp-Session-Id": sid}
            elif path == "/mcp" and isinstance(body, dict) and body.get("method") == "initialize":
                extra = {"Mcp-Session-Id": uuid.uuid4().hex}
            return self._send(200, resp, extra)

        if path.startswith("/tools/"):
            name = path[len("/tools/"):]
            try:
                result = tool_layer.call_tool(name, body)
            except KeyError as e:
                return self._send(404, {"error": str(e),
                                        "available": list(tool_layer.TOOLS)})
            except TypeError as e:
                return self._send(400, {"error": "入参不合法", "detail": str(e)})
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": type(e).__name__, "detail": str(e)})
            return self._send(200, result)

        return self._send(404, {"error": "not found", "path": path})

    def log_message(self, fmt, *args):
        sys.stderr.write("[http] %s - %s\n" % (self.address_string(), fmt % args))


def main():
    global _ARGS
    ap = argparse.ArgumentParser(description="粉尘涉爆判定工具集 HTTP 外壳")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--token", default="", help="开启 Bearer 鉴权时填写的 token")
    _ARGS = ap.parse_args()

    srv = ThreadingHTTPServer((_ARGS.host, _ARGS.port), Handler)
    print("已启动：http://%s:%d" % (_ARGS.host, _ARGS.port), file=sys.stderr)
    print("  工具清单  GET  /tools", file=sys.stderr)
    print("  OpenAPI   GET  /openapi.json", file=sys.stderr)
    print("  直调      POST /tools/judge", file=sys.stderr)
    print("  JSON-RPC  POST /rpc", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止", file=sys.stderr)


if __name__ == "__main__":
    main()
