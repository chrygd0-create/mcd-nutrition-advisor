#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦当劳 MCP Server 最小客户端（Streamable HTTP）。

用途：让 nutrition_calculator.py 在脱离 WorkBuddy 的情况下也能独立拉到官方数据，
方便开发者调试与二次开发。

Token 从环境变量读取，代码与日志中均不出现真实 Token。
    Windows PowerShell:  $env:MCD_MCP_TOKEN = "你的token"
    macOS / Linux:      export MCD_MCP_TOKEN="你的token"

用法:
    python mcd_client.py tools                      # 列出全部可用工具
    python mcd_client.py call list-nutrition-foods   # 调用工具并保存到 nutrition.json
    python mcd_client.py call available-coupons --out coupons.json
"""

import json
import os
import sys
import urllib.request
import urllib.error

ENDPOINT = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"
TIMEOUT = 30


def token():
    t = os.environ.get("MCD_MCP_TOKEN", "").strip()
    if not t:
        sys.exit("[error] 未找到环境变量 MCD_MCP_TOKEN，请先设置后再运行。")
    return t


_session_id = None


def rpc(method, params=None, notify=False):
    """发一次 JSON-RPC 请求，返回解析后的 result。"""
    global _session_id
    payload = {"jsonrpc": "2.0", "method": method}
    if not notify:
        payload["id"] = 1
    if params is not None:
        payload["params"] = params

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token()}",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    if _session_id:
        headers["Mcp-Session-Id"] = _session_id

    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                _session_id = sid
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code == 401:
            sys.exit("[error] 401：MCP Token 无效或已过期，请在控制台重新激活。")
        if e.code == 429:
            sys.exit("[error] 429：触发限流（600 次/分钟），请降低频率后重试。")
        sys.exit(f"[error] HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"[error] 网络不可达: {e.reason}（如在代理环境，确认代理已配置）")

    if not body.strip():
        return None
    # Streamable HTTP 可能返回 SSE 格式
    if body.lstrip().startswith("event:") or body.lstrip().startswith("data:"):
        for line in body.splitlines():
            if line.startswith("data:"):
                body = line[5:].strip()
                break
    data = json.loads(body)
    if "error" in data:
        sys.exit(f"[error] MCP 返回错误: {data['error']}")
    return data.get("result")


def handshake():
    rpc("initialize", {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "mcd-nutrition-advisor", "version": "1.0.0"},
    })
    rpc("notifications/initialized", {}, notify=True)


def call_tool(name, args=None):
    result = rpc("tools/call", {"name": name, "arguments": args or {}})
    if not result:
        return None
    # MCP 工具返回是 content 数组，正文在 text 里
    out = []
    for block in result.get("content", []):
        if block.get("type") == "text":
            text = block["text"]
            try:
                out.append(json.loads(text))
            except json.JSONDecodeError:
                out.append(text)
    return out[0] if len(out) == 1 else (out or result)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    handshake()

    if cmd == "tools":
        tools = rpc("tools/list").get("tools", [])
        for t in tools:
            print(f"{t['name']}\t{t.get('description', '')[:70]}")
        print(f"\n共 {len(tools)} 个工具", file=sys.stderr)
        return

    if cmd == "call":
        if len(sys.argv) < 3:
            sys.exit("用法: python mcd_client.py call <tool_name> [--out 文件.json]")
        name = sys.argv[2]
        out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
        data = call_tool(name)
        text = json.dumps(data, ensure_ascii=False, indent=2)
        if out:
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"已保存到 {out}", file=sys.stderr)
        else:
            print(text)
        return

    sys.exit(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()