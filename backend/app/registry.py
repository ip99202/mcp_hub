from __future__ import annotations

from typing import Dict, List

from .models import ServerConfig, ToolBinding


class InMemoryRegistry:
    """서버/툴 바인딩 정보를 메모리에 저장하는 간단한 레지스트리.

    - 프로세스 메모리에만 존재하므로 앱 재시작 시 초기화됨
    - CRUD 및 간단 통계(stat) 제공
    """
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
        """등록된 서버/툴의 개수를 요약해 반환한다."""
        num_servers = len(self._servers)
        num_tools = sum(len(tools) for tools in self._tools_by_server.values())
        return {"servers": num_servers, "tools": num_tools}


registry = InMemoryRegistry()


