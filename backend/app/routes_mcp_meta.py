from __future__ import annotations

from typing import Dict, Any, List

from fastapi import APIRouter

from .registry import registry


router = APIRouter(prefix="/mcp", tags=["mcp-meta"])


@router.post("/initialize")
async def initialize() -> Dict[str, Any]:
    """클라이언트 초기화 응답을 반환한다(MCP 메타 정보)."""
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
    """서버 스코프의 툴 목록을 MCP 메타 형식으로 반환한다."""
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
    """서버 스코프 초기화 응답을 반환한다."""
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
    # 일부 클라이언트가 POST /tools/list를 기대하는 경우를 위한 변형
    return await tools_list(server_id)


@router.get("/resources/list")
async def resources_list() -> Dict[str, Any]:
    """리소스 목록(현재 빈 배열)을 반환."""
    return {"resources": []}


@router.get("/resources/read")
async def resources_read() -> Dict[str, Any]:
    """리소스 읽기 스텁(현재 None)."""
    return {"content": None}


