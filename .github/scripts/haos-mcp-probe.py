# Runs inside the MCPHub App container: list the tools of both Home Assistant
# MCP servers and check that MCPHub registered them.
import json
import urllib.request

HEADERS = {"Content-Type": "application/json",
           "Accept": "application/json, text/event-stream"}


def post(url, body, session=None):
    headers = dict(HEADERS, **({"Mcp-Session-Id": session} if session else {}))
    request = urllib.request.Request(url, json.dumps(body).encode(), headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.headers.get("Mcp-Session-Id"), response.read().decode()


def tools(url):
    session, _ = post(url, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "haos-ci", "version": "1"}}})
    post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    return post(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session)[1].count('"inputSchema"')


def count(url):
    try:
        return tools(url)
    except Exception as error:
        print("MCP_PROBE_ERROR", url, type(error).__name__, error)
        return 0


with open("/data/mcphub/mcp_settings.json", encoding="utf-8") as handle:
    servers = json.load(handle)["mcpServers"]
official = count("http://127.0.0.1:8097/mcp")
unofficial = count("http://127.0.0.1:8096/mcp")
registered = {"HomeAssistant MCP (official)", "HomeAssistant MCP (unofficial)"} <= set(servers)
if official and unofficial and registered:
    print(f"MCP_PROBE_OK official={official} unofficial={unofficial}")
else:
    print(f"MCP_PROBE_WAIT official={official} unofficial={unofficial} registered={registered}")
