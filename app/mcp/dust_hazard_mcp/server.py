# -*- coding: utf-8 -*-
"""
MCP 服务（stdio 传输，纯标准库，零依赖）
=========================================

把 tools.py 的 6 个工具挂成 MCP 工具，供 AgentArts、Claude Desktop、
任意 MCP 客户端调用。

启动：
    python server.py

协议要点（MCP stdio）：
- 传输：stdin/stdout 上的**按行分隔 JSON-RPC 2.0**（不是 LSP 的 Content-Length 头）
- stdout 只允许出现协议报文；所有日志走 stderr
- 支持方法：initialize / notifications/initialized / ping / tools/list / tools/call
"""

from __future__ import annotations

import json
import sys
import traceback

try:  # 包内导入
    from . import tools as tool_layer
except ImportError:  # 直接运行脚本时兜底
    import tools as tool_layer

SERVER_NAME = "dust-hazard-judge"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2024-11-05"

_LOG_PREFIX = "[mcp] "


def log(msg):
    sys.stderr.write(_LOG_PREFIX + str(msg) + "\n")
    sys.stderr.flush()


def _ok(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _err(msg_id, code, message, data=None):
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": e}


def handle_initialize(msg_id, params):
    client_proto = (params or {}).get("protocolVersion") or DEFAULT_PROTOCOL
    log("initialize: client protocol=%s clientInfo=%s"
        % (client_proto, json.dumps((params or {}).get("clientInfo") or {}, ensure_ascii=False)))
    return _ok(msg_id, {
        "protocolVersion": client_proto,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": "粉尘涉爆重大事故隐患判定工具集。"
                        "判定请调用 judge；条款查询用 list_clauses / clause_detail / clause_search；"
                        "出文书用 render_doc。判定逻辑确定，同一输入永远得到同一结论。",
    })


def handle_tools_list(msg_id):
    return _ok(msg_id, {"tools": tool_layer.tools_manifest()})


def handle_tools_call(msg_id, params):
    params = params or {}
    name = params.get("name")
    args = params.get("arguments") or {}
    if not name:
        return _err(msg_id, -32602, "tools/call 缺少 name")
    try:
        result = tool_layer.call_tool(name, args)
    except KeyError as e:
        return _err(msg_id, -32602, "未知工具", {"detail": str(e)})
    except TypeError as e:
        return _err(msg_id, -32602, "入参不合法", {"detail": str(e)})
    except Exception as e:  # 工具内部异常：转成工具级错误，不打断会话
        log("tool %r failed:\n%s" % (name, traceback.format_exc()))
        return _ok(msg_id, {
            "content": [{"type": "text",
                         "text": json.dumps({"error": type(e).__name__,
                                             "message": str(e)}, ensure_ascii=False)}],
            "isError": True,
        })

    text = json.dumps(result, ensure_ascii=False, indent=2)
    return _ok(msg_id, {
        "content": [{"type": "text", "text": text}],
        "structuredContent": result,
        "isError": False,
    })


def dispatch(msg):
    """处理一条 JSON-RPC 报文；返回响应字典，或 None（通知类不需要响应）。"""
    if not isinstance(msg, dict):
        return _err(None, -32600, "不是合法的 JSON-RPC 报文")

    method = msg.get("method")
    msg_id = msg.get("id")
    is_notification = "id" not in msg

    if method == "initialize":
        return handle_initialize(msg_id, msg.get("params"))
    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return _ok(msg_id, {})
    if method == "tools/list":
        return handle_tools_list(msg_id)
    if method == "tools/call":
        return handle_tools_call(msg_id, msg.get("params"))
    if method in ("resources/list", "resources/templates/list"):
        return _ok(msg_id, {"resources": []})
    if method == "prompts/list":
        return _ok(msg_id, {"prompts": []})

    if is_notification:
        log("忽略未知通知：%s" % method)
        return None
    return _err(msg_id, -32601, "不支持的方法：%s" % method)


def main():
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except Exception:
            pass

    log("server started: %s v%s, tools=%d"
        % (SERVER_NAME, SERVER_VERSION, len(tool_layer.TOOLS)))

    for raw in sys.stdin:
        # 去掉 UTF-8 BOM：Windows 管道与部分客户端会在首行带 BOM
        line = raw.lstrip("\ufeff").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            resp = _err(None, -32700, "JSON 解析失败: %s" % e)
        else:
            try:
                resp = dispatch(msg)
            except Exception as e:
                log("dispatch failed:\n%s" % traceback.format_exc())
                resp = _err(msg.get("id") if isinstance(msg, dict) else None,
                            -32603, "内部错误: %s" % e)
        if resp is None:
            continue
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    log("stdin closed, server exiting")


if __name__ == "__main__":
    main()
