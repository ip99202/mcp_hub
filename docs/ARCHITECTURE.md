## MCP Hub 아키텍처 및 로직 설명서

본 문서는 프로젝트 전반 구조와 핵심 로직을 코드 기준으로 압축 정리한다. 예시와 실제 호출 흐름을 함께 제공한다.

---

### TL;DR
- **목표**: OpenAPI 없이도 임의의 REST API를 등록하면 곧바로 MCP Tool처럼 호출(SSE) 가능
- **구성**: FastAPI + 인메모리 레지스트리 + FastMCP 런타임 임베드 + React 대시보드
- **호출 경로**: `POST /mcp/{serverId}/{toolName}` → SSE 스트림(`tool_call.started` → `output.delta` → `tool_call.completed|error`)

---

## 1) 백엔드 구조 (FastAPI)

- `backend/app/main.py`
  - 앱 생성, CORS, 라우터 마운트, `/healthz` 등
  - 서버 시작 시 `lifespan`에서 데모 서버/툴 자동 등록(FakeStore, Fruits) 및 FastMCP 서브앱 마운트
- `backend/app/routes_api.py`
  - 허브 관리용 API: 서버/툴 CRUD, 통계
- `backend/app/routes_mcp.py`
  - MCP 스타일 진입점: `POST /mcp/{server}/{tool}` → SSE
  - `POST /mcp/{server}`: `initialize`, `tools.list`, `tools.call` 호환 처리
- `backend/app/routes_mcp_meta.py`
  - MCP 메타 엔드포인트(호환성): `/mcp/initialize`, `/{server}/tools/list` 등
- `backend/app/http_adapter.py`
  - REST 바인딩 호출 어댑터: URL/Headers/Query/Body 조립 → `httpx` 요청 → 응답 가공(JSONPath pick)
- `backend/app/fastmcp_runtime.py`
  - FastMCP 인스턴스, 툴 동적 등록/해제, 서버별 SSE 서브앱 마운트
- `backend/app/registry.py`
  - 인메모리 레지스트리: 서버/툴 보관 및 조회
- `backend/app/models.py`, `backend/app/schemas.py`
  - 데이터 모델 및 요청 스키마 정의

---

## 2) 핵심 데이터 모델(요약)

```python
# backend/app/models.py
class AuthType(str, Enum):
    bearer = "bearer"; header = "header"; query = "query"; none = "none"

class AuthConfig(BaseModel):
    type: AuthType = AuthType.none
    key: Optional[str] = None
    value: Optional[str] = None

class ServerConfig(BaseModel):
    name: str
    baseUrl: str
    auth: AuthConfig = Field(default_factory=AuthConfig)
    defaultHeaders: Dict[str, str] = Field(default_factory=dict)
    active: bool = True

class HttpMethod(str, Enum):
    GET = "GET"; POST = "POST"; PUT = "PUT"; PATCH = "PATCH"; DELETE = "DELETE"

class ParamMapping(BaseModel):
    path: Dict[str, str] = {}
    query: Dict[str, str] = {}
    headers: Dict[str, str] = {}
    body: Dict[str, str] = {}
    rawBody: Optional[str] = None

class ResponseMapping(BaseModel):
    pick: Optional[str] = None  # JSONPath

class ToolBinding(BaseModel):
    name: str
    description: Optional[str]
    method: HttpMethod
    pathTemplate: str
    paramMapping: ParamMapping = Field(default_factory=ParamMapping)
    inputSchema: Mapping[str, Any]  # JSON Schema
    responseMapping: Optional[ResponseMapping] = None
    active: bool = True
```

- `schemas.CallRequest`: `{"args": { ... }}` 형태로 MCP 툴 인자 전달

---

## 3) 인메모리 레지스트리

- 서버/툴 Upsert, Delete, List, 통계 제공
- DB 없이 프로세스 메모리에 보관(MVP)

```python
# backend/app/registry.py
class InMemoryRegistry:
    def upsert_server(self, server_id: str, cfg: ServerConfig) -> None: ...
    def list_servers(self) -> Dict[str, ServerConfig]: ...
    def upsert_tool(self, server_id: str, tool_name: str, binding: ToolBinding) -> None: ...
    def list_tools(self, server_id: str) -> Dict[str, ToolBinding]: ...
    def stats(self) -> Dict[str, int]:  # {servers, tools}
```

---

## 4) REST 호출 어댑터(`http_adapter.py`)

등록된 `ServerConfig` + `ToolBinding` + `args` 를 이용해 HTTP 요청을 조립한다.

핵심 로직:
- `pathTemplate` 플레이스홀더 → `paramMapping.path` 로 치환(누락 시 `BindingError`)
- 헤더/쿼리/바디 매핑 적용, 서버 인증(`AuthType`) 자동 주입
- `rawBody` 키가 지정되면 해당 인자를 원본 문자열/JSON으로 그대로 전송
- 응답이 JSON이면 `jsonpath-ng`로 선택 추출(`responseMapping.pick`), 아니면 원문 텍스트

```python
async def call_via_binding(server: ServerConfig, tool: ToolBinding, args: Dict[str, Any]) -> Dict[str, Any]:
    path = _interpolate_path(tool.pathTemplate, tool.paramMapping.path, args)
    url = server.baseUrl.rstrip('/') + '/' + path.lstrip('/')
    headers = _build_headers(server.defaultHeaders, tool.paramMapping.headers, args, server.auth.type, server.auth.key, server.auth.value)
    query = _build_query(tool.paramMapping.query, args, server.auth.type, server.auth.key, server.auth.value)
    json_body, raw_body = _build_body(tool.paramMapping.body, tool.paramMapping.rawBody, args)
    resp = await httpx.AsyncClient(...).request(tool.method.value, url, params=query, headers=headers, json=json_body if raw_body is None else None, content=raw_body)
    data = resp.json() if 'application/json' in resp.headers.get('content-type','') else resp.text
    picked = jsonpath_pick(data, tool.responseMapping.pick) if tool.responseMapping and isinstance(data, (dict, list)) else data
    return { 'status_code': resp.status_code, 'headers': dict(resp.headers), 'url': str(resp.request.url), 'data': picked }
```

예시 1) Path/Query 매핑 + Bearer 인증 자동 주입
```json
// ServerConfig.auth: { "type": "bearer", "value": "sk-xxx" }
// ToolBinding: GET /users/{id}, path={"id":"userId"}, query={"q":"query"}
{
  "args": { "userId": 42, "query": "name:kim" }
}
// → 요청: GET {baseUrl}/users/42?q=name:kim
// → 헤더: Authorization: Bearer sk-xxx
```

예시 2) Raw Body 전송
```json
// ToolBinding: POST /echo, paramMapping.rawBody = "payload"
{
  "args": { "payload": { "a": 1, "b": "x" } }
}
// → Content-Type은 호출자 책임(일반적으로 JSON). raw body 그대로 전송
```

에러 규칙(중요):
- `pathTemplate` 치환 누락 → 400/500 계열로 SSE `tool_call.error`에 메시지 포함
- JSON Schema 검증 실패 → 400 `schema_validation_error: ...` (아래 SSE 흐름 참조)

---

## 5) FastMCP 런타임 임베드(`fastmcp_runtime.py`)

- 전역 `fastmcp_server` + 서버별 `FastMCP` 인스턴스 관리
- `register_tool_with_fastmcp(serverId, toolName)` 호출 시 내부 어댑터 함수로 FastMCP 툴 등록
- 서버별 서브앱을 `/mcp-servers/{serverId}` 경로에 마운트(SSE)

세션/메시지 경로 및 세션 ID 정규화
- FastMCP 서브앱은 `GET /sse`(세션 생성)와 `POST /messages`(메시지 전송)를 제공한다.
- hub는 ASGI 래퍼(`MessagesNormalizerASGI`)를 서브앱에 적용하여, 쿼리의 `session_id`를 항상 "32자 hex(하이픈 없음)"으로 정규화한다. 이는 FastMCP가 내부적으로 `UUID(hex=...)`를 사용하기 때문.
- 기능 플래그: `MCP_SESSION_NORMALIZE`(기본값 `1`). `0|false`로 비활성화 가능.

주의: 인메모리 세션과 워커
- FastMCP의 SSE 세션 저장소는 인메모리이며 프로세스(워커) 간 공유되지 않는다. Uvicorn 멀티 워커 환경에서 `GET /sse`와 `POST /messages`가 서로 다른 워커로 라우팅되면 404가 발생할 수 있다.
- 운영 권장: `UVICORN_WORKERS=1`(단일 워커)로 구동하거나, 외부 공유 스토어(예: Redis) 기반 세션 매니저를 도입/확장.

등록 흐름:
```python
async def _tool_fn(args):
    result = await call_via_binding(server_cfg, binding, args or {})
    return result.get("data")

fastmcp_server.add_tool(FunctionTool.from_function(_tool_fn, name=f"{serverId}.{toolName}"))
get_or_create_fastmcp(serverId).add_tool(FunctionTool.from_function(_tool_fn, name=toolName))
```

---

## 6) MCP 호출 라우팅(`routes_mcp.py`)

진입점: `POST /mcp/{serverId}/{toolName}` → `EventSourceResponse`

핵심 단계:
1. 서버/툴 존재 및 활성 상태 확인(비활성 시 403)
2. (선택) `jsonschema.validate(args, inputSchema)` 검증 → 실패 시 400
3. 우선 FastMCP 툴 호출 시도 → 실패 시 HTTP 어댑터 폴백
4. 결과를 `output.delta` 이벤트로 1회 전송 후, `tool_call.completed`
5. 예외 발생 시 `tool_call.error`

SSE 이벤트 예시:
```text
event: tool_call.started
data: {"server":"ipify","tool":"get_ip"}

event: output.delta
data: {"ip":"203.0.113.10"}

event: tool_call.completed
data: {"status":200}
```

호환 엔드포인트(`POST /mcp/{serverId}`):
- `{ "method": "initialize" }` → MCP 메타 응답
- `{ "method": "tools.list" }` → 등록된 툴 목록(JSON Schema 포함)
- `{ "name": "toolName", "args": { ... } }` → `tools.call` 폴백(서버 스코프)

---

## 7) 앱 초기화 및 데모 시드(`main.py`)

- `lifespan`에서 다음 시드가 자동 등록됨:
  - `fakestore_api`: 상품 CRUD 툴 일체(`/products`, `/products/{id}`)
  - `fruits_api`: 목록/생성/수정/삭제(`/fruits`, `/fruits/{id}`), 중첩 객체 예시(`nutrients`)
- 각 툴은 `inputSchema`가 포함되어 있어 호출 시 JSON Schema 검증됨
- FastMCP 글로벌(`/mcp-sdk`) 및 서버별(`/mcp-servers/{id}`) SSE 서브앱 마운트

예시: `get_product_by_id` 인자 스키마
```json
{
  "type": "object",
  "properties": { "id": { "type": "integer" } },
  "required": ["id"]
}
```

---

## 8) 프론트엔드 대시보드(React, shadcn/ui)

- 파일: `frontend/src/App.tsx`
- 주요 기능
  - 서버 CRUD: 이름, `baseUrl`, 인증(`bearer|header|query|none`), 기본 헤더, 활성/비활성
  - 툴 CRUD: `name/description/method/pathTemplate`, `paramMapping(path/query/headers/body/rawBody)`, `inputSchema`, `responseMapping.pick`
  - 툴 테스트: 모달에서 SSE 결과 원문 라인 스트림으로 표시
  - 통계 카드: 서버/툴 전체/활성 개수 표시(`/api/stats`)

테스트 호출 흐름(요약):
```ts
const res = await fetch(`/mcp/${serverId}/${toolName}`, {
  method: 'POST', headers: { 'Accept': 'text/event-stream', 'Content-Type': 'application/json' },
  body: JSON.stringify({ args })
})
// ReadableStream 으로 라인 단위 표시
```

툴 목록 로딩:
- 특정 서버 선택 시 → `/api/tools/{serverId}`
- 전체 보기 시 → 모든 서버의 툴을 합쳐 복합 키(`${serverId}::${toolName}`)로 표시

---

## 9) API 표면(요약)

- 관리용
  - `GET /api/servers` / `POST /api/servers/{serverId}` / `DELETE /api/servers/{serverId}`
  - `GET /api/tools/{serverId}` / `GET /api/tools/{serverId}/{tool}` / `POST /api/tools/{serverId}/{tool}` / `DELETE /api/tools/{serverId}/{tool}`
  - `GET /api/stats` → { servers, activeServers, tools, activeTools }
- MCP/호환
  - `POST /mcp/{serverId}/{toolName}` → SSE 호출
  - `POST /mcp/{serverId}` → `initialize`/`tools.list`/`tools.call` 폴백
  - `GET|HEAD /mcp/{serverId}` → 클라이언트 핸드셰이크 호환
  - 메타: `POST /mcp/initialize`, `GET|POST /mcp/{serverId}/tools/list`, `POST /mcp/{serverId}/initialize`
- 기타
  - `GET /healthz`, `GET /_internal/registry`, `GET /_internal/fastmcp/tools`

---

## 10) 엔드투엔드 예시

예시 A) Ipify 서버 + `get_ip` 툴
1. 서버 등록
```json
{ "name":"ipify", "baseUrl":"https://api.ipify.org", "auth": {"type":"none"}, "defaultHeaders": {"Accept":"application/json"}, "active": true }
```
2. 툴 등록
```json
{
  "name":"get_ip", "method":"GET", "pathTemplate":"/", 
  "paramMapping": { "query": { "format":"format" } },
  "inputSchema": { "type":"object", "properties": { "format": {"type":"string","enum":["json"] } } },
  "active": true
}
```
3. 호출(SSE)
```json
POST /mcp/ipify/get_ip  { "args": { "format": "json" } }
```
수신 이벤트(예):
```text
event: output.delta
data: {"ip":"203.0.113.10"}
```

예시 B) FakeStore 상품 상세 조회
```json
POST /mcp/fakestore_api/get_product_by_id  { "args": { "id": 1 } }
```
응답 데이터(요약):
```json
{ "id":1, "title":"...", "price":109.95, "category":"men's clothing", "image":"..." }
```

예시 C) Fruits 생성(중첩 객체 포함)
```json
POST /mcp/fruits_api/create_fruit
{
  "args": {
    "name":"Mikan", "color":"Orange", "origin":"JP",
    "calories": 35, "season":"Winter",
    "nutrients": { "vitaminC":"high", "fiber":"medium" }
  }
}
```
Body 매핑은 최상위 키들을 그대로 JSON 바디에 투영하며, `nutrients` 같은 중첩 객체도 그대로 전달된다.

---

## 11) 검증/에러 처리

- 입력 검증: `jsonschema.validate(args, inputSchema)`
  - 실패 시: `400 schema_validation_error: ...` → SSE `tool_call.error`로도 통지
- 경로 치환 실패: 즉시 예외 → SSE `tool_call.error`
- 응답 처리: `content-type`이 JSON이 아니면 `text`로 취급
- JSONPath 선택: 다중 매치 시 배열 반환, 파서 오류 시 전체 JSON 반환
- 활성 제어: `server.active==False` 또는 `tool.active==False` → 403

세션/메시지 관련 유의사항
- `session_id` 정규화: 허브는 하이픈 유무와 무관하게 수신된 값을 UUID로 파싱 후 32자 hex로 통일한다. 클라이언트는 SSE가 내려준 endpoint의 `session_id`를 그대로 사용하는 것을 권장.
- 404(`Could not find session`) 발생 조건: (a) 존재하지 않는/만료된 세션, (b) 멀티 워커로 인해 세션이 다른 워커에만 존재하는 경우. 전자의 경우 SSE 재초기화, 후자의 경우 단일 워커 권장.

---

## 12) 운영/확장 포인트

- 저장소: 현재 인메모리(MVP). 필요 시 영구 저장소로 교체
- 인증: Bearer/Header/Query 지원. OAuth2 등 확장은 서버 레벨에서 추가 가능
- 전송: 현재 SSE만. 추후 stdio/Streamable HTTP 추가 가능
- 자동 임포트: OpenAPI→툴 자동 생성(향후)
- 리밋/재시도/레이트리밋: `http_adapter` 레벨에 미들웨어성 확장 가능

세션과 워커 구성
- 단일 워커 권장: `UVICORN_WORKERS=1` (멀티 워커 시 세션 분산으로 404 가능)
- 세션 표준화 플래그: `MCP_SESSION_NORMALIZE=1`(기본). 필요 시 끌 수 있음
- 장기적으로는 외부 세션 스토어(예: Redis) 연동 또는 FastMCP upstream에 공유 스토어 지원 기여 고려

---

## 13) 참고 파일

- FakeStore 툴 등록 가이드: `FAKESTORE_API_GUIDE.md`
- PRD: `prd.md`


