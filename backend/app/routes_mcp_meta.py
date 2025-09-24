from __future__ import annotations

from typing import Dict, Any, List

from fastapi import APIRouter

from .registry import registry


router = APIRouter(prefix="/mcp", tags=["mcp-meta"])


@router.post("/initialize")
async def initialize() -> Dict[str, Any]:
    return {
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": "mcp_hub", "version": "0.1.0"},
        "capabilities": {
            "tools": {},
            "resources": {},
        },
        "transport": "sse",
    }


@router.get("/{server_id}/tools/list")
async def tools_list(server_id: str) -> Dict[str, Any]:
    tools = registry.list_tools(server_id)
    items = []
    for name, binding in tools.items():
        items.append(
            {
                "name": name,
                "description": binding.description or "",
                "inputSchema": binding.inputSchema,
                "parameters": binding.inputSchema,
            }
        )
    return {"tools": items}


# Server-scoped initialize for clients that set base URL per server
@router.post("/{server_id}/initialize")
async def initialize_scoped(server_id: str) -> Dict[str, Any]:
    return {
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": f"mcp_hub:{server_id}", "version": "0.1.0"},
        "capabilities": {
            "tools": {},
            "resources": {},
        },
        "transport": "sse",
    }


@router.post("/{server_id}/tools/list")
async def tools_list_post(server_id: str) -> Dict[str, Any]:
    # POST variant for clients expecting POST /tools/list
    return await tools_list(server_id)


@router.get("/resources/list")
async def resources_list() -> Dict[str, Any]:
    return {"resources": []}


@router.get("/resources/read")
async def resources_read() -> Dict[str, Any]:
    return {"content": None}


