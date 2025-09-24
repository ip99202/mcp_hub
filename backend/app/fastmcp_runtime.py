from __future__ import annotations

from typing import Any, Dict, Optional, Set
import os
import logging
from uuid import UUID
from urllib.parse import parse_qsl, urlencode

from fastmcp import FastMCP
from fastmcp.tools.tool import FunctionTool

from .registry import registry
from .http_adapter import call_via_binding


fastmcp_server = FastMCP(name="MCP Hub")

# Server-scoped FastMCP instances and dynamic mounts
_server_fastmcp: Dict[str, FastMCP] = {}
_mounted_servers: Set[str] = set()
_app_ref: Optional[Any] = None  # Avoid FastAPI import cycle


logger = logging.getLogger(__name__)


def _normalize_uuid_if_possible(value: str) -> str:
    """Return 32-hex (no hyphens) canonical UUID string if value looks like a UUID.

    FastMCP's /messages expects `session_id` as 32-hex (UUID(hex=...)).
    Accept hyphenated or 32-hex input and normalize to 32-hex.
    Return input unchanged if not a valid UUID.
    """
    if not isinstance(value, str) or not value:
        return value
    candidate = value.strip()
    # Strip hyphens and lowercase for validation
    c2 = candidate.replace("-", "").strip().lower()
    if len(c2) == 32 and all(ch in "0123456789abcdef" for ch in c2):
        try:
            # Validate by constructing UUID from hex, then return hex form
            u = UUID(hex=c2)
            return u.hex
        except Exception:
            return value
    # Try parsing generic string (may include hyphens), then emit hex
    try:
        u = UUID(candidate)
        return u.hex
    except Exception:
        return value


class MessagesNormalizerASGI:
    """ASGI wrapper that normalizes `session_id` query param for /messages requests."""

    def __init__(self, app: Any, message_path: str = "/messages") -> None:
        self.app = app
        self.message_path = message_path.rstrip("/") or "/messages"

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> Any:
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        # Parse query string
        raw_qs: bytes = scope.get("query_string", b"")
        try:
            pairs = parse_qsl(raw_qs.decode("utf-8"), keep_blank_values=True)
        except Exception:
            pairs = []
        if not pairs:
            return await self.app(scope, receive, send)

        # Normalize session_id (and sessionId as a courtesy)
        changed = False
        new_pairs = []
        sid_in: Optional[str] = None
        for k, v in pairs:
            if k in ("session_id", "sessionId"):
                sid_in = v
                sid_norm = _normalize_uuid_if_possible(v)
                if sid_norm != v:
                    changed = True
                    new_pairs.append((k, sid_norm))
                else:
                    new_pairs.append((k, v))
            else:
                new_pairs.append((k, v))

        if changed:
            norm_qs = urlencode(new_pairs, doseq=True)
            scope = dict(scope)
            scope["query_string"] = norm_qs.encode("utf-8")
            try:
                logger.info("messages.normalize applied path=%s session_id.in=%s", path, sid_in)
            except Exception:
                pass

        return await self.app(scope, receive, send)


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

    subapp = create_sse_app(
        server=fastmcp_server,
        message_path="/messages",
        sse_path="/sse",
        auth=None,
        debug=False,
    )
    # Optional normalization wrapper
    if os.getenv("MCP_SESSION_NORMALIZE", "1") not in ("0", "false", "False"):
        subapp = MessagesNormalizerASGI(subapp, message_path="/messages")
    return subapp


def build_fastmcp_sse_app_for(server_id: str):
    from fastmcp.server.http import create_sse_app

    scoped = get_or_create_fastmcp(server_id)
    subapp = create_sse_app(
        server=scoped,
        message_path="/messages",
        sse_path="/sse",
        auth=None,
        debug=False,
    )
    if os.getenv("MCP_SESSION_NORMALIZE", "1") not in ("0", "false", "False"):
        subapp = MessagesNormalizerASGI(subapp, message_path="/messages")
    return subapp


def ensure_server_mounted(server_id: str) -> None:
    if _app_ref is None:
        return
    if server_id in _mounted_servers:
        return
    subapp = build_fastmcp_sse_app_for(server_id)
    _app_ref.mount(f"/mcp-servers/{server_id}", subapp)
    _mounted_servers.add(server_id)


