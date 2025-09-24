from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from .registry import registry
from .schemas import CallRequest
from pydantic import BaseModel
from .http_adapter import call_via_binding
from .fastmcp_runtime import fastmcp_server, tool_key


router = APIRouter(prefix="/mcp", tags=["mcp"])
@router.get("/{server_id}")
async def mcp_base_get(server_id: str) -> dict:
    # Cursor가 연결 체크 용도로 GET을 호출하는 경우가 있어 200을 돌려 호환성 보장
    servers = registry.list_servers()
    if server_id not in servers:
        raise HTTPException(status_code=404, detail="server not found")
    return {"ok": True, "server": server_id}


@router.head("/{server_id}")
async def mcp_base_head(server_id: str):
    # Langflow 등이 HEAD로 핸드셰이크 확인 시 200 반환
    servers = registry.list_servers()
    if server_id not in servers:
        raise HTTPException(status_code=404, detail="server not found")
    return {}


@router.post("/{server_id}")
async def mcp_base_post(server_id: str, request: Request):
    """Cursor SSE 호환을 위한 진입점.
    - initialize: {"method":"initialize"} → 메타 응답 JSON 반환
    - tools.list: {"method":"tools.list"} → 도구 목록 JSON 반환
    - tools.call: {"name":"toolName","args":{}} → SSE 스트림 반환 (기존 call_tool 위임)
    - 그 외: 단순 ok
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    method = body.get("method")
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": f"mcp_hub:{server_id}", "version": "0.1.0"},
            "capabilities": {"tools": {}, "resources": {}},
            "transport": "sse",
        }
    if method == "tools.list":
        tools = registry.list_tools(server_id)
        items = []
        for name, binding in tools.items():
            items.append({
                "name": name,
                "description": binding.description or "",
                "inputSchema": binding.inputSchema,
                "parameters": binding.inputSchema,
            })
        return {"tools": items}

    # tools.call 형태 폴백: name/args 조합을 허용
    tool_name = body.get("name")
    if tool_name:
        args = body.get("args") or {}
        return await call_tool(server_id, tool_name, CallRequest(args=args))

    return {"ok": True}


@router.post("/{server_id}/{tool_name}")
async def call_tool(server_id: str, tool_name: str, req: CallRequest) -> EventSourceResponse:
    servers = registry.list_servers()
    if server_id not in servers:
        raise HTTPException(status_code=404, detail="server not found")
    tools = registry.list_tools(server_id)
    if tool_name not in tools:
        raise HTTPException(status_code=404, detail="tool not found")

    server = servers[server_id]
    tool = tools[tool_name]

    if not server.active:
        raise HTTPException(status_code=403, detail="server inactive")
    if not tool.active:
        raise HTTPException(status_code=403, detail="tool inactive")

    async def event_stream() -> AsyncGenerator[dict, None]:
        yield {"event": "tool_call.started", "data": json.dumps({"server": server_id, "tool": tool_name})}
        try:
            # Validate args with JSON Schema if provided
            try:
                from jsonschema import validate  # type: ignore
                if tool.inputSchema:
                    validate(instance=req.args, schema=tool.inputSchema)
            except Exception as ve:
                raise HTTPException(status_code=400, detail=f"schema_validation_error: {ve}")

            data_payload = None
            status_code = 200
            # Prefer FastMCP runtime if tool is registered
            try:
                tr = await fastmcp_server._call_tool(tool_key(server_id, tool_name), req.args)
                r = tr.to_mcp_result()
                if isinstance(r, tuple):
                    # (content, structured)
                    data_payload = r[1]
                else:
                    # list[ContentBlock] → fallback serialize to text lines
                    def _cb_to_str(cb: Any) -> str:
                        try:
                            # Pydantic model
                            return cb.model_dump_json()
                        except Exception:
                            return str(cb)
                    data_payload = {"content": [ _cb_to_str(cb) for cb in r ]}
            except Exception:
                # Fallback to direct HTTP adapter
                result = await call_via_binding(server, tool, req.args)
                data_payload = result.get("data")
                status_code = result.get("status_code", 200)

            # Stream one chunk
            yield {"event": "output.delta", "data": json.dumps(data_payload)}
            yield {"event": "tool_call.completed", "data": json.dumps({"status": status_code})}
        except Exception as e:
            yield {"event": "tool_call.error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_stream())


# Standard MCP-style tools.call with server scoping in the path
class ToolCall(BaseModel):
    name: str
    args: dict | None = None


@router.post("/{server_id}/tools/call")
async def tools_call(server_id: str, body: ToolCall) -> EventSourceResponse:
    call_args = body.args or {}
    return await call_tool(server_id, body.name, CallRequest(args=call_args))

