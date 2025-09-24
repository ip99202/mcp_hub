from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, HTTPException

from .models import ServerConfig, ToolBinding
from .registry import registry
from .fastmcp_runtime import register_tool_with_fastmcp, deregister_tool_with_fastmcp
from .fastmcp_runtime import ensure_server_mounted


router = APIRouter(prefix="/api", tags=["api"])


# Servers
@router.get("/servers")
async def list_servers() -> Dict[str, ServerConfig]:
    return registry.list_servers()


@router.get("/stats")
async def global_stats() -> Dict[str, int]:
    servers = registry.list_servers()
    total_servers = len(servers)
    active_servers = sum(1 for s in servers.values() if getattr(s, "active", True))

    total_tools = 0
    active_tools = 0
    for sid in servers.keys():
        tools = registry.list_tools(sid)
        total_tools += len(tools)
        active_tools += sum(1 for t in tools.values() if getattr(t, "active", True))

    return {
        "servers": total_servers,
        "activeServers": active_servers,
        "tools": total_tools,
        "activeTools": active_tools,
    }


@router.get("/servers/{server_id}")
async def get_server(server_id: str) -> ServerConfig:
    servers = registry.list_servers()
    if server_id not in servers:
        raise HTTPException(status_code=404, detail="server not found")
    return servers[server_id]


@router.post("/servers/{server_id}")
async def upsert_server(server_id: str, cfg: ServerConfig) -> Dict[str, str]:
    registry.upsert_server(server_id, cfg)
    # Ensure SSE subapp mounted for this server
    ensure_server_mounted(server_id)
    return {"ok": "true"}


@router.delete("/servers/{server_id}")
async def delete_server(server_id: str) -> Dict[str, str]:
    registry.delete_server(server_id)
    return {"ok": "true"}


# Tools
@router.get("/tools/{server_id}")
async def list_tools(server_id: str) -> Dict[str, ToolBinding]:
    return registry.list_tools(server_id)


@router.get("/tools/{server_id}/{tool_name}")
async def get_tool(server_id: str, tool_name: str) -> ToolBinding:
    tools = registry.list_tools(server_id)
    if tool_name not in tools:
        raise HTTPException(status_code=404, detail="tool not found")
    return tools[tool_name]


@router.post("/tools/{server_id}/{tool_name}")
async def upsert_tool(server_id: str, tool_name: str, binding: ToolBinding) -> Dict[str, str]:
    registry.upsert_tool(server_id, tool_name, binding)
    # Register to FastMCP
    register_tool_with_fastmcp(server_id, tool_name)
    return {"ok": "true"}


@router.delete("/tools/{server_id}/{tool_name}")
async def delete_tool(server_id: str, tool_name: str) -> Dict[str, str]:
    registry.delete_tool(server_id, tool_name)
    deregister_tool_with_fastmcp(server_id, tool_name)
    return {"ok": "true"}


