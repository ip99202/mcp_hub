from __future__ import annotations

from fastapi import APIRouter

from .models import ServerConfig, AuthConfig, ToolBinding, HttpMethod, ParamMapping
from .registry import registry
from .http_adapter import call_via_binding


router = APIRouter(prefix="/_dev", tags=["dev"])


@router.post("/seed/httpbin")
async def seed_httpbin() -> dict:
    registry.upsert_server(
        "httpbin",
        ServerConfig(
            name="httpbin",
            baseUrl="https://httpbin.org",
            auth=AuthConfig(type="none"),
            defaultHeaders={"Accept": "application/json"},
        ),
    )

    registry.upsert_tool(
        "httpbin",
        "get_ip",
        ToolBinding(
            name="get_ip",
            description="get ip",
            method=HttpMethod.GET,
            pathTemplate="/ip",
            inputSchema={"type": "object", "properties": {}},
        ),
    )

    registry.upsert_tool(
        "httpbin",
        "delay",
        ToolBinding(
            name="delay",
            description="delay seconds",
            method=HttpMethod.GET,
            pathTemplate="/delay/{sec}",
            paramMapping=ParamMapping(path={"sec": "sec"}),
            inputSchema={
                "type": "object",
                "properties": {"sec": {"type": "integer", "minimum": 0, "maximum": 3}},
                "required": ["sec"],
            },
        ),
    )

    return registry.stats()


@router.post("/seed/ipify")
async def seed_ipify() -> dict:
    registry.upsert_server(
        "ipify",
        ServerConfig(
            name="ipify",
            baseUrl="https://api.ipify.org",
            auth=AuthConfig(type="none"),
            defaultHeaders={"Accept": "application/json"},
        ),
    )
    registry.upsert_tool(
        "ipify",
        "get_ip",
        ToolBinding(
            name="get_ip",
            description="get public ip",
            method=HttpMethod.GET,
            pathTemplate="/",
            paramMapping=ParamMapping(query={"format": "format"}),
            inputSchema={
                "type": "object",
                "properties": {"format": {"type": "string", "enum": ["json"]}},
            },
            responseMapping=None,
        ),
    )
    return registry.stats()


@router.post("/test/httpbin/{tool}")
async def test_httpbin(tool: str, args: dict) -> dict:
    server = registry.list_servers()["httpbin"]
    binding = registry.list_tools("httpbin")[tool]
    result = await call_via_binding(server, binding, args)
    return result


