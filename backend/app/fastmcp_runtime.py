from __future__ import annotations

from typing import Any, Dict, Optional, Set

from fastmcp import FastMCP
from fastmcp.tools.tool import FunctionTool

from .registry import registry
from .http_adapter import call_via_binding


fastmcp_server = FastMCP(name="MCP Hub")

# Server-scoped FastMCP instances and dynamic mounts
_server_fastmcp: Dict[str, FastMCP] = {}
_mounted_servers: Set[str] = set()
_app_ref: Optional[Any] = None  # Avoid FastAPI import cycle


def init_fastmcp_mounts(app: Any) -> None:
    global _app_ref
    _app_ref = app


def get_or_create_fastmcp(server_id: str) -> FastMCP:
    if server_id not in _server_fastmcp:
        _server_fastmcp[server_id] = FastMCP(name=f"MCP Hub:{server_id}")
    return _server_fastmcp[server_id]


def tool_key(server_id: str, tool_name: str) -> str:
    return f"{server_id}.{tool_name}"


def register_tool_with_fastmcp(server_id: str, tool_name: str) -> None:
    servers = registry.list_servers()
    tools = registry.list_tools(server_id)
    if server_id not in servers or tool_name not in tools:
        return
    server_cfg = servers[server_id]
    binding = tools[tool_name]

    async def _tool_fn(args: Dict[str, Any] | None = None) -> Any:
        provided_args: Dict[str, Any] = args or {}
        result: Dict[str, Any] = await call_via_binding(server_cfg, binding, provided_args)
        return result.get("data")

    # 1) Register to global FastMCP (for legacy/custom SSE)
    tool_global = FunctionTool.from_function(
        _tool_fn,
        name=tool_key(server_id, tool_name),
        description=binding.description or "",
    )
    fastmcp_server.add_tool(tool_global)

    # 2) Register to server-scoped FastMCP (for standard SSE per server)
    scoped = get_or_create_fastmcp(server_id)
    tool_scoped = FunctionTool.from_function(
        _tool_fn,
        name=tool_name,
        description=binding.description or "",
    )
    scoped.add_tool(tool_scoped)


def deregister_tool_with_fastmcp(server_id: str, tool_name: str) -> None:
    try:
        fastmcp_server.remove_tool(tool_key(server_id, tool_name))
    except Exception:
        pass
    try:
        scoped = _server_fastmcp.get(server_id)
        if scoped:
            scoped.remove_tool(tool_name)
    except Exception:
        pass


def build_fastmcp_sse_app():
    # Expose SSE endpoints under /mcp-sdk/{sse|messages} for global (legacy)
    from fastmcp.server.http import create_sse_app

    return create_sse_app(
        server=fastmcp_server,
        message_path="/messages",
        sse_path="/sse",
        auth=None,
        debug=False,
    )


def build_fastmcp_sse_app_for(server_id: str):
    from fastmcp.server.http import create_sse_app

    scoped = get_or_create_fastmcp(server_id)
    return create_sse_app(
        server=scoped,
        message_path="/messages",
        sse_path="/sse",
        auth=None,
        debug=False,
    )


def ensure_server_mounted(server_id: str) -> None:
    if _app_ref is None:
        return
    if server_id in _mounted_servers:
        return
    subapp = build_fastmcp_sse_app_for(server_id)
    _app_ref.mount(f"/mcp-servers/{server_id}", subapp)
    _mounted_servers.add(server_id)


