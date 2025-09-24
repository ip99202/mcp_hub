from __future__ import annotations

from typing import Dict, List

from .models import ServerConfig, ToolBinding


class InMemoryRegistry:
    def __init__(self) -> None:
        self._servers: Dict[str, ServerConfig] = {}
        self._tools_by_server: Dict[str, Dict[str, ToolBinding]] = {}

    # Server operations
    def upsert_server(self, server_id: str, cfg: ServerConfig) -> None:
        self._servers[server_id] = cfg
        self._tools_by_server.setdefault(server_id, {})

    def delete_server(self, server_id: str) -> None:
        self._servers.pop(server_id, None)
        self._tools_by_server.pop(server_id, None)

    def list_servers(self) -> Dict[str, ServerConfig]:
        return dict(self._servers)

    # Tool operations
    def upsert_tool(self, server_id: str, tool_name: str, binding: ToolBinding) -> None:
        self._tools_by_server.setdefault(server_id, {})[tool_name] = binding

    def delete_tool(self, server_id: str, tool_name: str) -> None:
        if server_id in self._tools_by_server:
            self._tools_by_server[server_id].pop(tool_name, None)

    def list_tools(self, server_id: str) -> Dict[str, ToolBinding]:
        return dict(self._tools_by_server.get(server_id, {}))

    # Introspection
    def stats(self) -> Dict[str, int]:
        num_servers = len(self._servers)
        num_tools = sum(len(tools) for tools in self._tools_by_server.values())
        return {"servers": num_servers, "tools": num_tools}


registry = InMemoryRegistry()


