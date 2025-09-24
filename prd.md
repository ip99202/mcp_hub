# 📑 Product Requirement Document (PRD)

**제품명**: MCP Hub & Admin Dashboard
**작성일자**: 2025-09-09
**작성자**: *(작성자 이름 기입)*

---

## 1. 개요 (Overview)

AI 기반 애플리케이션 및 도구에서 사용하는 **MCP(Model Context Protocol) 서버**를 통합 관리하기 위한 허브와 관리자 화면을 구축한다.

* **목표**: **OpenAPI 문서가 없어도** 일반 **REST API 등록**을 통해 MCP 툴로 바로 호출할 수 있는 중앙 허브 + 대시보드 제공.
* **문제**: 각 클라이언트(Continue, Langflow, OpenWebUI 등)의 MCP 연결 방식이 상이하고, 서버/툴 관리가 분산되어 있다.
* **해결**: **FastMCP 런타임**을 활용해 REST 바인딩을 MCP 툴로 동적으로 생성하고, **SSE 기반** 단일 인터페이스로 호출을 제공한다.

---

## 2. 목표 (Goals)

* MCP **필수 메서드** 지원: `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`
* **전송 방식: SSE만 지원** (향후 확장: stdio, Streamable HTTP)
* **서버/툴 관리 UI**: REST 바인딩을 등록/수정/삭제, 활성/비활성, 검색
* **DB 없이 동작**: LocalStorage/인메모리 저장 (MVP)

---

## 3. 범위 (Scope)

### 포함 (In Scope)

* **REST 바인딩 → MCP 툴 자동화** (수동 등록식)

  * 서버 단위: `baseUrl`, 인증, 공통 헤더
  * 툴 단위: `name/description`, `method`, `pathTemplate`, **파라미터 매핑**(path/query/header/body), 입력 **JSON Schema**, (옵션) 응답 매핑
* **SSE 호출 경로** 제공: `POST /mcp/{serverId}/{toolName}` (SSE 스트림)
* **Dashboard UI**: 서버/툴 CRUD, 검색/필터, 호출 테스트
* **저장소**: LocalStorage 기반(데모/MVP)

### 제외 (Out of Scope)

* stdio/Streamable HTTP 전송
* OpenAPI → 자동 임포트(향후)
* RBAC/멀티 유저
* 대규모 모니터링/코스트 관리
* 영구 DB

---

## 4. 주요 기능 (Features)

### 4.1 MCP 서버 (MVP)

* `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`
* (알림/notifications 계열은 제외 — 향후 확장)

### 4.2 Admin Dashboard (UI)

* **서버 관리**

  * 등록/수정/삭제: `name`, `baseUrl`, `auth`(bearer/header/query/none), `defaultHeaders(JSON)`
  * 활성/비활성, 검색/필터
* **툴 관리**

  * 등록/수정/삭제: `name`, `description`, `method(GET/POST/PUT/PATCH/DELETE)`, `pathTemplate`
  * **paramMapping**: `path/query/headers/body/rawBody` 매핑
  * **inputSchema(JSON Schema)** 편집/검증
  * (옵션) **responseMapping**: JSON 선택자(`pick`)로 결과 요약
  * 호출 테스트(SSE 결과 뷰)

---

## 5. 아키텍처 (Architecture)

* **FastMCP 런타임**: MCP 표준 메서드/전송을 제공하는 기반 라이브러리 사용
* **REST 바인딩 어댑터(Hub 내부)**: 등록된 바인딩대로 HTTP 요청을 조립/호출, 응답을 **SSE 델타**로 브리지
* **허브 구조**: 다중 서버/툴 레지스트리(인메모리/LocalStorage)
* **UI**: React + shadcn/ui + Tailwind

---

## 5-1. FastMCP 사용 계획 (MVP)

**목표**

* FastMCP를 **MCP 런타임 & 어댑터**로 사용해, Hub가 MCP 표준 메서드(`initialize`, `tools/list`, `tools/call`)를 그대로 노출한다.
* OpenAPI 문서 없이도 **수동 REST 바인딩**을 기반으로 **FastMCP 툴**을 동적으로 구성/등록한다.

**구성 요소**

* `FastMCP Runtime`: SSE 전송을 포함한 MCP 서버 실행 책임
* `BindingAdapter`: Hub에 등록된 Server/Tool 바인딩을 **FastMCP 툴**로 변환/등록
* `Transport (SSE)`: `POST /mcp/{serverId}/{toolName}` 요청을 FastMCP `tools/call`로 위임 → 결과를 SSE로 브리지

**동작 흐름**

1. **서버/툴 등록** → 바인딩 정보를 FastMCP 툴로 등록 (`register_tool`)
2. **툴 호출** → Hub에서 `fastmcp.call_tool(serverId, toolName, args)` 실행 → 델타/완료 이벤트를 SSE로 전달

---

## 6. 사용자 흐름 (User Flow)

1. Dashboard 접속
2. **서버 등록**: `baseUrl`, 인증/헤더 입력
3. **툴 등록**: `method`, `pathTemplate`, `paramMapping`, `inputSchema` 입력
4. 툴 선택 → 인자(JSON) 입력 → **SSE 호출 테스트**
5. 서버/툴 검색/수정/삭제, 활성/비활성 관리

---

## 6-1. 입력 Form 정의 (with Examples)

### A) MCP 서버 등록 Form

| 필드                     | 타입             | 필수  | 예시/Placeholder                     |
| ---------------------- | -------------- | --- | ---------------------------------- |
| **서버 이름 (name)**       | text           | ✅   | `Weather API`                      |
| **Base URL (baseUrl)** | text           | ✅   | `https://api.weather.com/v1`       |
| 인증 방식 (auth.type)      | select         | ❌   | `Bearer / Header / Query / None`   |
| 인증 키 (auth.key)        | text           | 조건부 | `X-API-Key`                        |
| 인증 값 (auth.value)      | text/password  | 조건부 | `abc123` or `Bearer sk-xxxxx`      |
| 기본 헤더 (defaultHeaders) | key-value JSON | ❌   | `{ "Accept": "application/json" }` |
| 활성화 (active)           | toggle         | ❌   | 기본: On                             |

**예시 JSON**

```json
{
  "name": "Weather API",
  "baseUrl": "https://api.weather.com/v1",
  "auth": { "type": "header", "key": "X-API-Key", "value": "abc123" },
  "defaultHeaders": { "Accept": "application/json" },
  "active": true
}
```

---

### B) MCP 툴 등록 Form

| 필드                               | 타입          | 필수  | 예시/Placeholder                                                                                                            |
| -------------------------------- | ----------- | --- | ------------------------------------------------------------------------------------------------------------------------- |
| **툴 이름 (name)**                  | text        | ✅   | `get_forecast`                                                                                                            |
| 설명 (description)                 | textarea    | ❌   | `국가/도시 기준 단기 예보 조회`                                                                                                       |
| **HTTP Method (method)**         | select      | ✅   | `GET`                                                                                                                     |
| **Path Template (pathTemplate)** | text        | ✅   | `/forecast/{country}`                                                                                                     |
| 입력 스키마 (inputSchema)             | JSON editor | ✅   | `{ "type":"object","properties":{ "country":{"type":"string"},"city":{"type":"string"} },"required":["country","city"] }` |
| Path 매핑 (paramMapping.path)      | key-value   | 조건부 | `{ "country": "country" }`                                                                                                |
| Query 매핑 (paramMapping.query)    | key-value   | ❌   | `{ "city": "city", "days": "days" }`                                                                                      |
| Header 매핑 (paramMapping.headers) | key-value   | ❌   | `{ "X-Api-Version": "apiVersion" }`                                                                                       |
| Body 매핑 (paramMapping.body)      | key-value   | ❌   | `{ "text": "text", "targetLang": "target" }`                                                                              |
| Raw Body (paramMapping.rawBody)  | text        | ❌   | `payload`                                                                                                                 |
| 응답 매핑 (responseMapping.pick)     | text        | ❌   | `$.forecast.daily`                                                                                                        |
| 활성화 (active)                     | toggle      | ❌   | 기본: On                                                                                                                    |

**예시 JSON (GET)**

```json
{
  "name": "get_forecast",
  "description": "국가/도시 기준 단기 예보",
  "method": "GET",
  "pathTemplate": "/forecast/{country}",
  "paramMapping": {
    "path": { "country": "country" },
    "query": { "city": "city", "days": "days" }
  },
  "inputSchema": {
    "type": "object",
    "properties": {
      "country": { "type": "string" },
      "city": { "type": "string" },
      "days": { "type": "integer", "default": 3 }
    },
    "required": ["country", "city"]
  },
  "responseMapping": { "pick": "$.forecast.daily" },
  "active": true
}
```

**예시 JSON (POST)**

```json
{
  "name": "translate",
  "description": "문장 번역",
  "method": "POST",
  "pathTemplate": "/translate",
  "paramMapping": {
    "body": { "text": "text", "targetLang": "target" }
  },
  "inputSchema": {
    "type": "object",
    "properties": {
      "text": { "type": "string" },
      "target": { "type": "string", "enum": ["en","ko","ja"], "default": "en" }
    },
    "required": ["text","target"]
  },
  "active": true
}
```

---

## 7. 기술 요구사항 (Tech Requirements)

* **Backend**: Python 3.11+ + `modelcontextprotocol/python-sdk` (FastMCP)

  * Hub 내부에 FastMCP 인스턴스를 **임베드**
  * 등록 시 툴 → FastMCP에 동적 등록, 호출 시 → FastMCP `tools/call` 실행
* **Frontend**: React, TypeScript, shadcn/ui, Tailwind
* **Persistence**: LocalStorage (MVP)
* **Deployment**: Docker (단일 서비스)

---

## 8. 운영 고려사항 (MVP)

* CORS 허용(개발/시연용), 기본 타임아웃
* (향후) HTTPS, 인증 토큰 저장 정책, 레이트리밋, 샘플링 로그/메트릭, 감사 추적

---

## 9. 툴 URL/바인딩 설계

### 서버(Server)

* `baseUrl` (예: `https://api.example.com/v1`)
* 인증: `type`(`bearer`/`header`/`query`/`none`), `key/value`
* `defaultHeaders`: 공통 헤더(JSON)

### 툴(Tool)

* `name`, `description`
* `method`: `GET|POST|PUT|PATCH|DELETE`
* `pathTemplate`: 예) `/forecast/{country}`
* **paramMapping**

  * `path`: `{ country: "country" }`
  * `query`: `{ days: "days", units: "units" }`
  * `headers`: `{ "X-Api-Version": "apiVersion" }`
  * `body`: `{ text: "$.text", targetLang: "$.target" }`
  * `rawBody`: `"payload"`
* **inputSchema** (JSON Schema)
* (옵션) **responseMapping**: `{ pick: "$.data.items" }`

### 호출 경로/프로토콜

* **`POST /mcp/{serverId}/{toolName}`** → **SSE 스트림**

  * 요청 바디: `{ "args": { ... } }`
  * 내부 동작: Hub → FastMCP `call_tool` 실행 → 델타를 SSE 이벤트로 중계
  * 이벤트: `tool_call.started` → `output.delta`\* → `tool_call.completed|error`

---

## 10. 네트워킹 및 라우팅

* **단일 허브 포트 + 경로 라우팅**

  * `POST /mcp/{serverId}/{toolName}` (SSE 호출)
  * `GET /api/servers`, `GET /api/tools/{serverId}` (목록 조회)
* (옵션) 서버 분리/스케일아웃은 향후

---

## 11. 향후 확장 (Future Work)

* **OpenAPI 임포트**: 스펙이 생기면 자동으로 툴 바인딩 생성
* stdio/Streamable HTTP 지원
* RBAC/멀티 유저, 영구 DB
* 실시간 모니터링, 비용/쿼터, 감사
* 파일 업로드/멀티파트, OAuth2 토큰 플로우 헬퍼
* 페이지네이션/재시도/레이트리밋 어댑터

