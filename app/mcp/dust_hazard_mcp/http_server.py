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
import os
import socket
import sys
import time
import traceback
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:  # 包内导入
    from . import tools as tool_layer
except ImportError:  # 直接运行脚本时兜底
    import tools as tool_layer

_ARGS = None

# ---------------------------------------------------------------------------
# Demo 页面托管（同源架构：页面与 API 同一个域名，浏览器侧零跨域）
# ---------------------------------------------------------------------------
_REPO_WEB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web")

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

# 平台主路径所需配置（未配置时自动跳过，页面降级到本地引擎）
PLATFORM_URL = os.environ.get(
    "AGENTARTS_URL",
    "https://01a19c34ab5473379710915943a56294.studio.agentarts.cn-southwest-2.huaweiapaas.com")
PLATFORM_KEY = os.environ.get("AGENTARTS_API_KEY", "").strip()


def _collect_text(obj, out=None):
    """从平台流式响应里尽力抽取文本片段。

    平台返回结构随 event 类型变化（content 是 Object），所以这里做宽容遍历：
    只收出现在 text / output / reply / answer / content 键上的字符串。
    """
    if out is None:
        out = []
    if isinstance(obj, str):
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                if k in ("text", "output", "reply", "answer", "content", "delta"):
                    out.append(v)
            else:
                _collect_text(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_text(v, out)
    return out


def _extract_facts(text):
    """降级路径用的粗糙关键词抽取（仅 Demo 兜底，不属于判定逻辑）。

    平台主路径由大模型节点做抽取；本地降级没有模型，只能用关键词把口语
    粗粒度映射成字段。抽不准就少给字段 -> 引擎自然回「待核实」，不会误判。
    判定本身仍完全由 engine/dust_judge.py 执行。
    """
    t = (text or "").strip()
    facts = {}
    if not t:
        return facts

    def has(*words):
        return any(w in t for w in words)

    if has("木质", "木头", "木粉", "木屑", "家具", "砂光"):
        facts["dust_collector.dust_kind"] = "wood"
    elif has("铝", "镁", "金属", "打磨", "抛光"):
        facts["dust_collector.dust_kind"] = "metal"

    if has("湿式", "水浴", "水帘"):
        facts["dust_collector.type"] = "wet"
    elif has("干式", "干除尘"):
        facts["dust_collector.type"] = "dry"
    elif has("没装除尘", "没有除尘", "没有除尘器", "无除尘系统"):
        facts["dust_collector.type"] = "none"

    measures = []
    if has("装了泄爆", "有泄爆", "泄爆片", "泄压片"):
        measures.append("vent")
    if has("惰化"):
        measures.append("inerting")
    if has("抑爆"):
        measures.append("suppression")
    if measures:
        facts["dust_collector.control_measures"] = measures

    if has("积尘", "木屑堆", "灰很厚", "粉尘很厚", "没清理", "没有清理",
           "清理制度", "没落实清理"):
        facts["dust.cleaning_not_implemented"] = True
    if has("沉降室", "地沟", "巷道", "当风道", "风道除尘"):
        facts["dust_collector.gravity_or_tunnel_duct"] = True
    if has("正压",):
        facts["dust_collector.positive_pressure"] = True
    if has("没卸灰", "没有卸灰", "缺卸灰", "未设卸灰", "没设锁气", "未设锁气", "没锁气"):
        facts["dust_collector.no_ash_discharge"] = True
    elif "锁气" in t and has("没", "未", "没有", "没装", "未装"):
        facts["dust_collector.no_ash_discharge"] = True
    if has("不防爆", "没防爆", "电线裸露", "闸刀", "私拉乱接"):
        facts["dust_area.electrical_not_proof"] = True
    if has("共用一套", "共用除尘", "互联互通", "串在一起"):
        facts["dust_collector.mixed_shared"] = True
    if has("宿舍", "办公室", "会议室", "休息室", "人员聚集"):
        facts["dust_area.layout_violation"] = True
    return facts


def _mentions_dust(text):
    """判断这句话是不是在讲粉尘涉爆现场（用于降级路径补默认领域）。"""
    t = text or ""
    return any(w in t for w in (
        "粉尘", "木粉", "木屑", "木质", "家具", "砂光", "打磨", "抛光",
        "铝", "镁", "除尘", "积尘", "车间", "涉爆"))


def _lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
        finally:
            s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


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
                                    "engine_version": tool_layer.ENGINE_VERSION,
                                    "platform_ready": bool(PLATFORM_KEY)})
        if path == "/tools":
            return self._send(200, {"tools": tool_layer.tools_manifest()})
        if path == "/openapi.json":
            return self._send(200, _openapi(self._base_url()))
        if path == "/api/status":
            return self._send(200, {"platform_ready": bool(PLATFORM_KEY),
                                    "platform_url": PLATFORM_URL,
                                    "engine_version": tool_layer.ENGINE_VERSION})
        if path in ("/", "/index.html"):
            return self._serve_file("index.html")
        if path.startswith("/web/") or path.startswith("/replay/"):
            return self._serve_file(path.lstrip("/"))
        return self._send(404, {"error": "not found", "path": path})

    def _serve_file(self, rel):
        """托管 web 目录下的静态文件：拒绝路径穿越、不列目录。"""
        base = os.path.abspath((_ARGS.web_dir if _ARGS and _ARGS.web_dir else _REPO_WEB_DIR))
        target = os.path.abspath(os.path.join(base, rel))
        if target != base and not target.startswith(base + os.sep):
            return self._send(403, {"error": "forbidden"})
        if not os.path.isfile(target):
            return self._send(404, {"error": "not found", "path": rel})
        ext = os.path.splitext(target)[1].lower()
        with open(target, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", _MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _platform_proxy(self, body):
        """主路径：服务端持 API Key 代理到 AgentArts 单智能体 API，浏览器永远不接触 Key。"""
        if not PLATFORM_KEY:
            return self._send(501, {"ok": False, "code": "NO_PLATFORM_KEY",
                                    "message": "未配置 AGENTARTS_API_KEY，主路径跳过，前端请降级到本地引擎"})
        body = body or {}
        query = (body.get("query") or "").strip()
        if not query:
            return self._send(400, {"ok": False, "code": "EMPTY_QUERY",
                                    "message": "query 不能为空"})
        sid = (body.get("session_id") or uuid.uuid4().hex)[:32]
        t0 = time.time()
        payload = json.dumps({"inputs": {"query": query}}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(PLATFORM_URL, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "text/event-stream, application/json")
        req.add_header("Authorization", "Bearer " + PLATFORM_KEY)
        req.add_header("x-hw-agentarts-session-id", sid)

        texts, events = [], 0
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                ctype = (r.headers.get("Content-Type") or "").lower()
                if "event-stream" in ctype:
                    for raw in r:
                        line = raw.decode("utf-8", "replace").strip()
                        if not line.startswith("data:"):
                            continue
                        chunk = line[5:].strip()
                        if not chunk or chunk == "[DONE]":
                            continue
                        try:
                            obj = json.loads(chunk)
                        except Exception:
                            continue
                        events += 1
                        _collect_text(obj, texts)
                else:
                    obj = json.loads(r.read().decode("utf-8", "replace"))
                    events = 1
                    _collect_text(obj, texts)
        except Exception as e:
            traceback.print_exc()
            return self._send(502, {"ok": False, "code": "PLATFORM_ERROR",
                                    "message": "%s: %s" % (type(e).__name__, e)})

        return self._send(200, {"ok": True, "chain": "platform", "session_id": sid,
                                "text": "".join(texts).strip(), "events": events,
                                "latency_ms": int((time.time() - t0) * 1000)})

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

        if path == "/api/judge":
            body = body or {}
            args = dict(body)
            query = args.get("query") or ""
            if not args.get("facts") and not args.get("payload") and query:
                # 降级路径没有大模型，用关键词兜底抽一层
                args["facts"] = _extract_facts(query)
            if not args.get("industry") and (args.get("facts") or _mentions_dust(query)):
                args["industry"] = "粉尘涉爆"
            args.pop("query", None)
            try:
                result = tool_layer.call_tool("judge", args)
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"error": type(e).__name__, "detail": str(e)})
            result["_chain"] = "local"
            try:
                result["_extracted_facts"] = args.get("facts") or {}
            except Exception:
                pass
            return self._send(200, result)

        if path == "/api/agent":
            return self._platform_proxy(body)

        if path == "/api/status":
            return self._send(200, {"platform_ready": bool(PLATFORM_KEY),
                                    "platform_url": PLATFORM_URL,
                                    "engine_version": tool_layer.ENGINE_VERSION})

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
    ap.add_argument("--web-dir", default="", help="Demo 页面目录（默认 <repo>/app/web）")
    _ARGS = ap.parse_args()

    srv = ThreadingHTTPServer((_ARGS.host, _ARGS.port), Handler)
    port = _ARGS.port
    print("=" * 62, file=sys.stderr)
    print("粉尘涉爆判定工具集 · HTTP 服务", file=sys.stderr)
    print("=" * 62, file=sys.stderr)
    print("  Demo 页面   http://127.0.0.1:%d/" % port, file=sys.stderr)
    if _ARGS.host == "0.0.0.0":
        for ip in _lan_ips():
            print("  局域网      http://%s:%d/" % (ip, port), file=sys.stderr)
    else:
        print("  提示：加 --host 0.0.0.0 可让局域网其它设备访问", file=sys.stderr)
    print("  工具清单    GET  /tools", file=sys.stderr)
    print("  OpenAPI     GET  /openapi.json", file=sys.stderr)
    print("  MCP 端点    POST /mcp", file=sys.stderr)
    print("  本地判定    POST /api/judge", file=sys.stderr)
    print("  平台代理    POST /api/agent %s"
          % ("(已配置 API Key)" if PLATFORM_KEY else "(未配置 AGENTARTS_API_KEY，将降级)"),
          file=sys.stderr)
    print("-" * 62, file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止", file=sys.stderr)


if __name__ == "__main__":
    main()
