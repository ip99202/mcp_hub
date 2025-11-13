# MCP Hub 주니어 온보딩 가이드
이 문서는 프로젝트를 처음 접한 개발자가 **전체 흐름과 세부 로직을 빠짐없이 이해**하도록 돕는 온보딩 가이드다. 실행 환경 구성부터 프런트↔백엔드↔외부 API까지의 데이터 흐름, 각 모듈의 역할과 코드 레벨 동작 방식을 순서대로 설명한다.

---

## 0. TL;DR (먼저 읽고 그림 잡기)
- **무엇을 하는가**: 임의의 REST API를 `ServerConfig`+`ToolBinding` 형태로 등록하면 곧바로 MCP 호환 SSE 툴로 호출할 수 있는 허브.
- **구성 요소**: FastAPI 백엔드(인메모리 레지스트리, FastMCP 런타임, HTTP 어댑터) + React/Vite 대시보드(UI).
- **핵심 흐름**: 프런트에서 서버/툴 등록 → `/api/*` 라우터가 레지스트리와 FastMCP를 갱신 → 사용자가 툴 호출 버튼 클릭 → `/mcp/{server}/{tool}` SSE → FastMCP 또는 HTTP 어댑터가 외부 REST API를 호출 → SSE 스트림으로 결과 반환.
- **현재 저장소**: 인메모리 MVP. 프로세스가 재시작되면 설정이 사라진다.

---

## 1. 시스템 한눈에 보기

```
[React Dashboard] ── fetch ──> [/api/* CRUD]
      │                               │
      │                               ▼
      │                      [InMemoryRegistry]
      │                               │
      └─(테스트/호출)─ POST /mcp/...    ─┴─> [FastAPI SSE 핸들러]
                                        │
                                        ├─ FastMCP 런타임 호출 (우선)
                                        └─ HTTP Adapter → 외부 REST API
```

- 프런트엔드는 `/api`, `/mcp` 경로를 프록시(개발 시 Vite, 운영 시 Nginx)로 백엔드(포트 8000)에 연결한다.
- 백엔드는 FastAPI 앱으로, 서버 시작 시 데모 서버/툴을 자동 등록하고 FastMCP SSE 서브앱을 마운트한다.
- FastMCP는 등록된 툴을 MCP 프로토콜 표준에 맞춰 SSE로 노출한다. 실패 시 HTTP 어댑터가 직접 REST API를 호출한다.

---

## 2. 실행 전 알아둘 것
- **필수 런타임**: Python 3.11+, Node 20+. 빠르게 보려면 `docker compose up -d`.
- **백엔드**: `uvicorn backend.app.main:app --reload --port 8000`
- **프런트**: `cd frontend && npm install && npm run dev` → http://localhost:5173
- **이미 등록된 데모**: `fakestore_api`, `fruits_api` 서버와 CRUD 툴 세트가 자동으로 올라온다.
- **상태 확인**: `GET /healthz`, `GET /api/stats`, `GET /_internal/registry`

---

## 3. 앱 부팅 시 무슨 일이 일어나는가

FastAPI 앱은 `lifespan` 컨텍스트에서 기본 서버와 툴을 등록하고, 각 서버의 SSE 서브앱을 동적으로 마운트한다.

```29:211:backend/app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        server_id = "fakestore_api"
        ensure_server_mounted(server_id)
        if server_id not in registry.list_servers():
            registry.upsert_server(server_id, ServerConfig(...))
        def ensure_tool(binding: ToolBinding) -> None:
            tools_local = registry.list_tools(server_id)
            if binding.name not in tools_local:
                registry.upsert_tool(server_id, binding.name, binding)
                register_tool_with_fastmcp(server_id, binding.name)
        # FakeStore 도구 4종 등록 ...
        fruits_server_id = "fruits_api"
        ensure_server_mounted(fruits_server_id)
        if fruits_server_id not in servers:
            registry.upsert_server(fruits_server_id, ServerConfig(...))
        # Fruits 도구 5종 등록 ...
    except Exception:
        pass
    yield
```

- `ensure_server_mounted`가 FastAPI 앱 객체에 `/mcp-servers/{serverId}` 경로의 FastMCP 서브앱을 마운트한다.
- 등록되지 않은 툴만 `registry.upsert_tool` → `register_tool_with_fastmcp` 순으로 추가한다.
- 실패해도 앱은 계속 뜨도록 `try/except`로 감싸놓았다.

앱 인스턴스를 만든 뒤 CORS, 라우터, 글로벌 FastMCP SSE 앱(`/mcp-sdk`)도 모두 여기서 설정한다. `/healthz`, `/sse/test`, `/ _internal/*` 같은 진단용 엔드포인트도 바로 확인 가능하다.

---

## 4. 데이터 모델과 인메모리 저장소

### 4.1 모델 정의
- **`ServerConfig`**: 이름, `baseUrl`, 인증 설정(`AuthConfig`), 기본 헤더, 활성 여부.
- **`ToolBinding`**: HTTP 메서드, 경로 템플릿, 인자→경로/쿼리/헤더/바디 매핑(`ParamMapping`), JSON Schema 입력 검증, 응답 후처리(`ResponseMapping.pick`).

```37:79:backend/app/models.py
class ToolBinding(BaseModel):
    name: str
    description: Optional[str] = None
    method: HttpMethod
    pathTemplate: str
    paramMapping: ParamMapping = Field(default_factory=ParamMapping)
    inputSchema: Mapping[str, Any]
    responseMapping: Optional[ResponseMapping] = None
    active: bool = True
```

### 4.2 인메모리 레지스트리
- 파이썬 딕셔너리 두 개(`_servers`, `_tools_by_server`)에 모든 구성을 저장한다.
- 서버/툴 CRUD, 전체 통계 반환 기능만 제공하는 MVP 구현.

```18:46:backend/app/registry.py
class InMemoryRegistry:
    def upsert_server(self, server_id: str, cfg: ServerConfig) -> None:
        self._servers[server_id] = cfg
        self._tools_by_server.setdefault(server_id, {})
    def upsert_tool(self, server_id: str, tool_name: str, binding: ToolBinding) -> None:
        self._tools_by_server.setdefault(server_id, {})[tool_name] = binding
    def list_tools(self, server_id: str) -> Dict[str, ToolBinding]:
        return dict(self._tools_by_server.get(server_id, {}))
    def stats(self) -> Dict[str, int]:
        num_servers = len(self._servers)
        num_tools = sum(len(tools) for tools in self._tools_by_server.values())
        return {"servers": num_servers, "tools": num_tools}
```

> ⚠️ **주의**: 인메모리이기 때문에 uvicorn 프로세스를 재시작하면 설정이 모두 초기화된다. 향후에는 DB 혹은 파일 백업을 붙여야 한다.

---

## 5. FastMCP 런타임 연결 구조

FastMCP는 MCP 표준 SSE 서버를 쉽게 구성할 수 있는 라이브러리다. 허브에서는 글로벌 인스턴스 하나와 서버별 인스턴스들을 동시에 관리한다.

```119:167:backend/app/fastmcp_runtime.py
def register_tool_with_fastmcp(server_id: str, tool_name: str) -> None:
    servers = registry.list_servers()
    tools = registry.list_tools(server_id)
    if server_id not in servers or tool_name not in tools:
        return
    server_cfg = servers[server_id]
    binding = tools[tool_name]

    async def _tool_fn(args: Dict[str, Any] | None = None) -> Any:
        provided_args = args or {}
        result = await call_via_binding(server_cfg, binding, provided_args)
        return result.get("data")

    tool_global = FunctionTool.from_function(
        _tool_fn,
        name=tool_key(server_id, tool_name),
        description=binding.description or "",
    )
    fastmcp_server.add_tool(tool_global)

    scoped = get_or_create_fastmcp(server_id)
    tool_scoped = FunctionTool.from_function(
        _tool_fn,
        name=tool_name,
        description=binding.description or "",
    )
    scoped.add_tool(tool_scoped)
```

- 글로벌 인스턴스는 `{server}.{tool}` 이름으로 등록되어 `/mcp-sdk` SSE 엔드포인트에서 공유된다.
- 서버 스코프 인스턴스는 `/mcp-servers/{server}/sse` 경로로 노출된다.
- `_tool_fn`은 HTTP 어댑터 결과의 `data` 필드만 반환해 MCP 컨텐츠로 사용한다.
- `MessagesNormalizerASGI` 래퍼가 `session_id`를 32자리 hex로 정규화해 클라이언트 호환성을 유지한다.

---

## 6. HTTP 어댑터: ToolBinding → REST 호출

툴 호출이 FastMCP로 처리되지 못하면 `call_via_binding`가 외부 REST API를 직접 호출한다. 경로 템플릿 치환, 인증 헤더, JSON Schema, JSONPath 후처리까지 모두 여기서 처리한다.

```93:167:backend/app/http_adapter.py
async def call_via_binding(server: ServerConfig, tool: ToolBinding, args: Dict[str, Any]) -> Dict[str, Any]:
    path = _interpolate_path(tool.pathTemplate, tool.paramMapping.path, args)
    url = server.baseUrl.rstrip("/") + "/" + path.lstrip("/")
    headers = _build_headers(server.defaultHeaders, tool.paramMapping.headers, args, server.auth.type, server.auth.key, server.auth.value)
    query = _build_query(tool.paramMapping.query, args, server.auth.type, server.auth.key, server.auth.value)
    json_body, raw_body = _build_body(tool.paramMapping.body, tool.paramMapping.rawBody, args)

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.request(
            tool.method.value,
            url,
            params=query or None,
            headers=headers or None,
            json=json_body if raw_body is None else None,
            content=raw_body,
        )

    content_type = resp.headers.get("content-type", "")
    ...
    if tool.responseMapping and tool.responseMapping.pick and response_json is not None:
        from jsonpath_ng import parse as jp_parse
        expr = jp_parse(tool.responseMapping.pick)
        matches = [m.value for m in expr.find(response_json)]
        picked = matches[0] if len(matches) == 1 else matches
```

동작 순서:
1. `pathTemplate`의 플레이스홀더를 `args` 값으로 치환한다. 누락되면 `BindingError`.
2. 서버 기본 헤더 + 툴 별 헤더 매핑 + 인증(베어러/커스텀 헤더/쿼리 파라미터)을 합친다.
3. 바디 매핑: 딕셔너리 매핑 또는 `rawBody` 키로 전체 페이로드 전달.
4. `httpx.AsyncClient`로 실제 요청 → 응답 JSON을 파싱하거나 텍스트로 보관.
5. `responseMapping.pick`이 있으면 `jsonpath-ng`로 필요한 부분만 추출한다.

---

## 7. MCP 라우터: SSE 툴 호출 처리

실제 툴 호출은 모두 `/mcp/{serverId}/{toolName}` 엔드포인트로 들어온다. 내부 로직은 다음과 같다.

```78:137:backend/app/routes_mcp.py
@router.post("/{server_id}/{tool_name}")
async def call_tool(server_id: str, tool_name: str, req: CallRequest) -> EventSourceResponse:
    servers = registry.list_servers()
    if server_id not in servers:
        raise HTTPException(status_code=404, detail="server not found")
    ...
    async def event_stream() -> AsyncGenerator[dict, None]:
        yield {"event": "tool_call.started", "data": json.dumps({"server": server_id, "tool": tool_name})}
        try:
            from jsonschema import validate
            if tool.inputSchema:
                validate(instance=req.args, schema=tool.inputSchema)
            try:
                tr = await fastmcp_server._call_tool(tool_key(server_id, tool_name), req.args)
                r = tr.to_mcp_result()
                ...
                data_payload = {"content": [_cb_to_str(cb) for cb in r]}
            except Exception:
                result = await call_via_binding(server, tool, req.args)
                data_payload = result.get("data")
            yield {"event": "output.delta", "data": json.dumps(data_payload)}
            yield {"event": "tool_call.completed", "data": json.dumps({"status": status_code})}
        except Exception as e:
            yield {"event": "tool_call.error", "data": json.dumps({"error": str(e)})}
```

SSE 스트림 이벤트 순서:
1. `tool_call.started` – 호출 시작 알림.
2. `output.delta` – 결과 payload (FastMCP 결과 또는 HTTP 폴백 결과).
3. `tool_call.completed` – 상태 코드 포함 완료 이벤트.
4. 에러 발생 시 `tool_call.error`.

추가 호환성:
- `POST /mcp/{server}`는 `initialize`, `tools.list`, `tools.call` JSON 프로토콜을 처리한다.
- `POST /mcp/{server}/tools/call`은 MCP 표준 바디(`{"name": "...", "args": {...}}`)를 SSE로 리디렉션한다.

---

## 8. 관리 API 라우터: 서버·툴 CRUD와 통계

프런트 대시보드가 사용하는 REST 엔드포인트들은 모두 `/api` 프리픽스에 있다.

```16:99:backend/app/routes_api.py
@router.get("/servers")
async def list_servers() -> Dict[str, ServerConfig]:
    return registry.list_servers()

@router.post("/servers/{server_id}")
async def upsert_server(server_id: str, cfg: ServerConfig) -> Dict[str, str]:
    registry.upsert_server(server_id, cfg)
    ensure_server_mounted(server_id)
    return {"ok": "true"}

@router.post("/tools/{server_id}/{tool_name}")
async def upsert_tool(server_id: str, tool_name: str, binding: ToolBinding) -> Dict[str, str]:
    registry.upsert_tool(server_id, tool_name, binding)
    register_tool_with_fastmcp(server_id, tool_name)
    return {"ok": "true"}
```

- 서버 저장 시 SSE 서브앱이 자동 마운트된다.
- 툴 저장 시 FastMCP 런타임에 즉시 등록된다.
- `/api/stats`는 전체/활성 서버/툴 개수를 요약해 프런트 Summary 카드에 전달한다.

---

## 9. 프런트엔드 대시보드 동작 원리

단일 파일(`frontend/src/App.tsx`)에 CRUD 폼, 리스트, 테스트 모달이 모두 들어 있다. 상태를 의도적으로 나눠 읽으면 전체 플로우가 명확해진다.

```62:224:frontend/src/App.tsx
const refreshStats = async () => {
  const data = await getJson('/api/stats')
  setStats({ servers: data?.servers || 0, tools: data?.tools || 0, activeServers: data?.activeServers ?? undefined, activeTools: data?.activeTools ?? undefined })
}
const upsertServer = async () => {
  const body = { name: serverName, baseUrl: serverBaseUrl, auth, defaultHeaders: headers, active: serverActive }
  const serverIdToUse = editingServerId || serverName.toLowerCase().replace(/\s+/g, '_')
  await post(`/api/servers/${serverIdToUse}`, body)
  await refreshServers()
  await refreshStats()
}
const upsertTool = async () => {
  const body = { name: toolName, description: toolDescription, method: httpMethod, pathTemplate, paramMapping: {...}, inputSchema, active: toolActive }
  if (responsePick?.trim()) body.responseMapping = { pick: responsePick.trim() }
  await post(`/api/tools/${serverToUse}/${toolNameToUse}`, body)
  await refreshTools(serverToUse)
  await refreshStats()
}
```

핵심 포인트:
- **폼 상태**: 서버/툴 각각에 대한 텍스트필드가 상태로 관리된다. 편집 시 기존 값을 fetch로 불러와 채운다.
- **CRUD 호출**: `post`, `del`, `getJson` 헬퍼를 통해 백엔드 `/api` 엔드포인트를 호출한다.
- **툴 테스트**: `fetch('/mcp/{server}/{tool}', { method: 'POST', headers: Accept: text/event-stream })`로 SSE를 열고, `ReadableStream`을 줄 단위로 읽어 모달에 로그로 출력한다.
- **서버 셀렉트**: 특정 서버 선택 시 해당 서버의 툴만 불러오고, "All Servers"일 때는 모든 서버의 툴을 `{serverId}::{toolName}` 키로 합친다.
- **로컬스토리지**: 최근에 호출한 `serverId`, `toolName`, `args`를 저장해 새로고침 후에도 폼이 유지된다.

테스트 모달 스트림 처리:

```352:394:frontend/src/App.tsx
const testTool = async (toolName: string, serverId: string) => {
  const res = await fetch(`/mcp/${serverId}/${toolName}`, {
    method: 'POST',
    headers: { 'Accept': 'text/event-stream', 'Content-Type': 'application/json' },
    body: JSON.stringify({ args: {} })
  })
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value)
    const lines = chunk.trim().split('\n')
    for (const line of lines) {
      if (line.trim()) setTestLog((l) => [...l, line])
    }
  }
}
```

---

## 10. 엔드투엔드 호출 시나리오 (UI → 외부 API)

1. **서버 등록**: 대시보드 `+ Add Server` → `/api/servers/{serverId}` POST → 레지스트리 및 FastMCP 서브앱 업데이트.
2. **툴 등록**: 해당 서버 선택 후 `+ Add Tool` → `/api/tools/{serverId}/{tool}` POST → 레지스트리/ FastMCP 등록.
3. **테스트 클릭**: `Test` 버튼 → `fetch('/mcp/{server}/{tool}', Accept: text/event-stream)` → SSE 스트림 구독.
4. **백엔드 처리**:
   - `routes_mcp.call_tool`이 JSON Schema 검증.
   - FastMCP 런타임에 등록돼 있으면 `_call_tool` 실행, 아니면 `call_via_binding`로 REST 호출.
   - 응답 데이터를 `output.delta`로 스트리밍.
5. **결과 확인**: 모달 로그에 이벤트 라인이 그대로 표시된다. JSONPath로 잘려나간 경우 `data`가 축약된 상태로 도착한다.

외부 API 호출 예시: FakeStore 상품 조회

```bash
curl -N \
  -H 'Accept: text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"args": {"id": 1}}' \
  http://localhost:8000/mcp/fakestore_api/get_product_by_id
```

대시보드에서도 동일한 SSE 흐름을 UI로 확인할 수 있다.

---

## 11. 확장 및 주의 체크리스트

- **지속성 도입**: 현재는 인메모리. RDB/Redis 등을 붙일 때는 `registry` 인터페이스를 기준으로 대체 클래스를 구현하면 된다.
- **동시성**: FastMCP 세션이 워커 간 공유되지 않으므로 uvicorn은 단일 워커(`UVICORN_WORKERS=1`)로 띄우거나 외부 세션 스토어를 붙인다.
- **에러 핸들링**: JSON Schema, 경로 치환, HTTP 호출 예외는 모두 `tool_call.error` 이벤트로 노출되므로 UI에서 사용자 친화적 메시지를 추가할 수 있다.
- **보안**: CORS가 `*`로 열려 있고 인증이 없다. 운영 시에는 API 키/세션 검증, TLS, rate limit을 추가한다.
- **신규 툴 템플릿**: `ParamMapping`을 적극 활용해 인자↔HTTP 요소 매핑을 명시하면 추후 UI에서 미리보기/유효성 검사를 제공하기 쉽다.

---

## 12. 빠른 참조 링크

- 전체 아키텍처 다이어그램: `docs/architecture.svg`
- 상세 아키텍처 요약: `docs/ARCHITECTURE.md`
- FakeStore API 설정 가이드: `docs/FAKESTORE_API_GUIDE.md`
- 제품 요구사항(PRD): `docs/prd.md`
- 스케일아웃 고려 사항: `docs/mcp_hub_scaleout_prd.md`


---

이 문서를 한 번 정독한 뒤에는 `docs/ARCHITECTURE.md`와 실제 코드 파일을 나란히 열어보며 흐름을 재구성해보자. 모듈 간 경로를 기억하고 나면, 새 API를 붙이거나 FastMCP 통합을 확장할 때 훨씬 빠르게 적응할 수 있다.


