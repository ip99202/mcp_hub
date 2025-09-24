from __future__ import annotations

import asyncio
import datetime as dt
from typing import AsyncGenerator, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from .registry import registry
from .routes_dev import router as dev_router
from .routes_mcp import router as mcp_router
from .routes_api import router as api_router
from .routes_mcp_meta import router as mcp_meta_router
from fastapi import APIRouter
from starlette.middleware import Middleware
from starlette.routing import Mount
from .fastmcp_runtime import (
    build_fastmcp_sse_app,
    fastmcp_server,
    init_fastmcp_mounts,
    ensure_server_mounted,
)
from .models import ServerConfig, ToolBinding, HttpMethod, ParamMapping
from .fastmcp_runtime import register_tool_with_fastmcp


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-register default server/tools on startup (migrated from on_event)
    try:
        server_id = "fakestore_api"
        ensure_server_mounted(server_id)
        if server_id not in registry.list_servers():
            registry.upsert_server(
                server_id,
                ServerConfig(
                    name="FakeStore API",
                    baseUrl="https://fakestoreapi.com",
                    defaultHeaders={"Accept": "application/json"},
                    active=True,
                ),
            )

        # Helper to upsert and register a tool only if missing
        def ensure_tool(binding: ToolBinding) -> None:
            tools_local = registry.list_tools(server_id)
            if binding.name not in tools_local:
                registry.upsert_tool(server_id, binding.name, binding)
                register_tool_with_fastmcp(server_id, binding.name)

        # Products: GET /products
        ensure_tool(
            ToolBinding(
                name="get_all_products",
                description="모든 상품 조회",
                method=HttpMethod.GET,
                pathTemplate="/products",
                inputSchema={"type": "object", "properties": {}},
                active=True,
            )
        )

        # Products: POST /products
        ensure_tool(
            ToolBinding(
                name="add_product",
                description="상품 생성",
                method=HttpMethod.POST,
                pathTemplate="/products",
                paramMapping=ParamMapping(
                    body={
                        "title": "title",
                        "price": "price",
                        "description": "description",
                        "category": "category",
                        "image": "image",
                    }
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "price": {"type": "number"},
                        "description": {"type": "string"},
                        "category": {"type": "string"},
                        "image": {"type": "string", "format": "uri"},
                    },
                    "required": ["title", "price"],
                },
                active=True,
            )
        )

        # Products: GET /products/{id}
        ensure_tool(
            ToolBinding(
                name="get_product_by_id",
                description="상품 상세 조회",
                method=HttpMethod.GET,
                pathTemplate="/products/{id}",
                paramMapping=ParamMapping(path={"id": "id"}),
                inputSchema={
                    "type": "object",
                    "properties": {"id": {"type": "integer"}},
                    "required": ["id"],
                },
                active=True,
            )
        )

        # Products: PUT /products/{id}
        ensure_tool(
            ToolBinding(
                name="update_product",
                description="상품 수정",
                method=HttpMethod.PUT,
                pathTemplate="/products/{id}",
                paramMapping=ParamMapping(
                    path={"id": "id"},
                    body={
                        "title": "title",
                        "price": "price",
                        "description": "description",
                        "category": "category",
                        "image": "image",
                    },
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "title": {"type": "string"},
                        "price": {"type": "number"},
                        "description": {"type": "string"},
                        "category": {"type": "string"},
                        "image": {"type": "string", "format": "uri"},
                    },
                    "required": ["id"],
                },
                active=True,
            )
        )

        # Products: DELETE /products/{id}
        ensure_tool(
            ToolBinding(
                name="delete_product",
                description="상품 삭제",
                method=HttpMethod.DELETE,
                pathTemplate="/products/{id}",
                paramMapping=ParamMapping(path={"id": "id"}),
                inputSchema={
                    "type": "object",
                    "properties": {"id": {"type": "integer"}},
                    "required": ["id"],
                },
                active=True,
            )
        )

        # --- Fruits API server and tools ---
        fruits_server_id = "fruits_api"
        ensure_server_mounted(fruits_server_id)
        servers = registry.list_servers()
        if fruits_server_id not in servers:
            registry.upsert_server(
                fruits_server_id,
                ServerConfig(
                    name="Fruits API",
                    baseUrl="https://api.mocktailapi.com/api/",
                    defaultHeaders={"Accept": "application/json"},
                    active=True,
                ),
            )

        def ensure_fruits_tool(binding: ToolBinding) -> None:
            tools_local = registry.list_tools(fruits_server_id)
            if binding.name not in tools_local:
                registry.upsert_tool(fruits_server_id, binding.name, binding)
                register_tool_with_fastmcp(fruits_server_id, binding.name)

        # Fruits: GET /fruits (pagination)
        ensure_fruits_tool(
            ToolBinding(
                name="get_fruits",
                description="과일 목록 조회 (페이지네이션)",
                method=HttpMethod.GET,
                pathTemplate="/fruits",
                paramMapping=ParamMapping(
                    query={
                        "page": "page",
                        "pageSize": "pageSize",
                    }
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "minimum": 1},
                        "pageSize": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                },
                active=True,
            )
        )

        # Fruits: POST /fruits
        ensure_fruits_tool(
            ToolBinding(
                name="create_fruit",
                description="과일 생성",
                method=HttpMethod.POST,
                pathTemplate="/fruits",
                paramMapping=ParamMapping(
                    body={
                        "name": "name",
                        "color": "color",
                        "origin": "origin",
                        "calories": "calories",
                        "season": "season",
                        "type": "type",
                        "weight": "weight",
                        "nutrients": "nutrients",
                        "taste": "taste",
                        "availability": "availability",
                    }
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "color": {"type": "string"},
                        "origin": {"type": "string"},
                        "calories": {"type": "integer", "minimum": 0},
                        "season": {"type": "string", "enum": ["Spring", "Summer", "Autumn", "Winter"]},
                        "type": {"type": "string"},
                        "weight": {"type": "string"},
                        "nutrients": {
                            "type": "object",
                            "properties": {
                                "vitaminC": {"type": "string"},
                                "fiber": {"type": "string"},
                                "potassium": {"type": "string"},
                            },
                            "additionalProperties": False
                        },
                        "taste": {"type": "string"},
                        "availability": {"type": "string"}
                    },
                    "required": ["name", "color"],
                },
                active=True,
            )
        )

        # Fruits: GET /fruits/{id}
        ensure_fruits_tool(
            ToolBinding(
                name="get_fruit_by_id",
                description="과일 상세 조회",
                method=HttpMethod.GET,
                pathTemplate="/fruits/{id}",
                paramMapping=ParamMapping(path={"id": "id"}),
                inputSchema={
                    "type": "object",
                    "properties": {"id": {"type": "integer", "minimum": 1}},
                    "required": ["id"],
                },
                active=True,
            )
        )

        # Fruits: PUT /fruits/{id}
        ensure_fruits_tool(
            ToolBinding(
                name="update_fruit",
                description="과일 수정",
                method=HttpMethod.PUT,
                pathTemplate="/fruits/{id}",
                paramMapping=ParamMapping(
                    path={"id": "id"},
                    body={
                        "name": "name",
                        "color": "color",
                        "origin": "origin",
                        "calories": "calories",
                        "season": "season",
                        "type": "type",
                        "weight": "weight",
                        "nutrients": "nutrients",
                        "taste": "taste",
                        "availability": "availability",
                    }
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "minimum": 1},
                        "name": {"type": "string"},
                        "color": {"type": "string"},
                        "origin": {"type": "string"},
                        "calories": {"type": "integer", "minimum": 0},
                        "season": {"type": "string", "enum": ["Spring", "Summer", "Autumn", "Winter"]},
                        "type": {"type": "string"},
                        "weight": {"type": "string"},
                        "nutrients": {
                            "type": "object",
                            "properties": {
                                "vitaminC": {"type": "string"},
                                "fiber": {"type": "string"},
                                "potassium": {"type": "string"},
                            },
                            "additionalProperties": False
                        },
                        "taste": {"type": "string"},
                        "availability": {"type": "string"}
                    },
                    "required": ["id"],
                },
                active=True,
            )
        )

        # Fruits: DELETE /fruits/{id}
        ensure_fruits_tool(
            ToolBinding(
                name="delete_fruit",
                description="과일 삭제",
                method=HttpMethod.DELETE,
                pathTemplate="/fruits/{id}",
                paramMapping=ParamMapping(path={"id": "id"}),
                inputSchema={
                    "type": "object",
                    "properties": {"id": {"type": "integer", "minimum": 1}},
                    "required": ["id"],
                },
                active=True,
            )
        )
    except Exception:
        # Fail silently; app should still boot
        pass

    yield


app = FastAPI(title="MCP Hub MVP", version="0.1.0", lifespan=lifespan)
init_fastmcp_mounts(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {"ok": True, "ts": dt.datetime.utcnow().isoformat() + "Z"}


@app.get("/sse/test")
async def sse_test() -> EventSourceResponse:
    async def event_generator() -> AsyncGenerator[dict, None]:
        yield {"event": "tool_call.started", "data": "sse-test"}
        for i in range(5):
            await asyncio.sleep(0.5)
            yield {"event": "output.delta", "data": f"tick {i}"}
        yield {"event": "tool_call.completed", "data": "done"}

    return EventSourceResponse(event_generator())


@app.get("/_internal/registry")
async def registry_stats() -> dict:
    return registry.stats()


app.include_router(dev_router)
app.include_router(mcp_router)
app.include_router(api_router)
app.include_router(mcp_meta_router)

# Mount FastMCP SSE app under /mcp-sdk (global)
fastmcp_app = build_fastmcp_sse_app()
app.mount("/mcp-sdk", fastmcp_app)

@app.get("/_internal/fastmcp/tools")
async def list_fastmcp_tools():
    tools = await fastmcp_server.get_tools()
    return sorted(list(tools.keys()))


# (startup migrated to lifespan)

