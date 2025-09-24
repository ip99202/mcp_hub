from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

import httpx
from pydantic import ValidationError

from .models import ServerConfig, ToolBinding, AuthType, HttpMethod


class BindingError(Exception):
    pass


def _interpolate_path(path_template: str, path_mapping: Dict[str, str], args: Dict[str, Any]) -> str:
    """pathTemplate에 지정된 {placeholder}를 실제 args 값으로 치환한다.

    - path_mapping: {세그먼트키: 인자키} 형태. 예) {"id": "productId"}
    - args: 실제 툴 호출 시 전달된 인자 딕셔너리
    - 치환 후 남은 중괄호가 있으면 바인딩 누락으로 판단해 예외 발생
    """
    path = path_template
    for segment_key, arg_key in path_mapping.items():
        if arg_key not in args:
            raise BindingError(f"Missing path arg: {arg_key}")
        path = path.replace("{" + segment_key + "}", str(args[arg_key]))
    if "{" in path or "}" in path:
        # Some placeholders left unsubstituted
        raise BindingError("Unresolved path placeholders in pathTemplate")
    return path


def _build_headers(base_headers: Dict[str, str], header_mapping: Dict[str, str], args: Dict[str, Any], auth: AuthType, auth_key: Optional[str], auth_value: Optional[str]) -> Dict[str, str]:
    """요청 헤더를 구성한다.

    우선 서버 기본 헤더를 복사하고, 바인딩의 header 매핑에 따라 args 값을 덮어쓴다.
    추가로 서버의 인증 설정(AuthType)에 따라 Authorization/커스텀 헤더를 자동 세팅한다.
    """
    headers: Dict[str, str] = dict(base_headers)

    # Map per-binding headers
    for header_name, arg_key in header_mapping.items():
        if arg_key in args and args[arg_key] is not None:
            headers[header_name] = str(args[arg_key])

    # Apply auth
    if auth == AuthType.bearer and auth_value:
        headers.setdefault("Authorization", auth_value if auth_value.lower().startswith("bearer") else f"Bearer {auth_value}")
    elif auth == AuthType.header and auth_key and auth_value:
        headers.setdefault(auth_key, auth_value)

    return headers


def _build_query(query_mapping: Dict[str, str], args: Dict[str, Any], auth: AuthType, auth_key: Optional[str], auth_value: Optional[str]) -> Dict[str, Any]:
    """쿼리스트링을 구성한다.

    - query_mapping에 정의된 키만 args에서 뽑아 사용한다.
    - 인증 타입이 query인 경우 auth_key=auth_value를 기본값으로 추가한다.
    """
    query: Dict[str, Any] = {}
    for q_name, arg_key in query_mapping.items():
        if arg_key in args and args[arg_key] is not None:
            query[q_name] = args[arg_key]
    if auth == AuthType.query and auth_key and auth_value:
        query.setdefault(auth_key, auth_value)
    return query


def _build_body(body_mapping: Dict[str, str], raw_body_key: Optional[str], args: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """요청 바디를 구성한다.

    우선 rawBody 설정이 있으면 그 키의 값을 그대로 문자열/JSON 직렬화하여 content로 보낸다.
    그렇지 않다면 body 매핑에 정의된 키만 추려 JSON 바디(dict)로 보낸다.
    반환값은 (json_body, raw_body) 쌍이며 둘 중 하나만 사용된다.
    """
    if raw_body_key:
        raw_val = args.get(raw_body_key)
        if raw_val is None:
            return None, None
        return None, raw_val if isinstance(raw_val, str) else json.dumps(raw_val)

    if body_mapping:
        body: Dict[str, Any] = {}
        for body_key, arg_key in body_mapping.items():
            if arg_key in args and args[arg_key] is not None:
                body[body_key] = args[arg_key]
        return body or None, None
    return None, None


async def call_via_binding(server: ServerConfig, tool: ToolBinding, args: Dict[str, Any]) -> Dict[str, Any]:
    """등록된 서버/툴 바인딩 정보를 이용해 실제 HTTP 호출을 수행한다.

    - URL: 서버 baseUrl + pathTemplate 치환 결과
    - Headers/Query/Body: 서버 기본값 + 바인딩 매핑 + 인증 설정을 반영
    - 응답: content-type이 JSON이면 파싱, 아니면 텍스트로 보관
    - responseMapping.pick이 있으면 jsonpath-ng로 필요한 부분만 추출
    """
    # Compose URL
    path = _interpolate_path(tool.pathTemplate, tool.paramMapping.path, args)
    url = server.baseUrl.rstrip("/") + "/" + path.lstrip("/")

    # Compose headers/query/body
    headers = _build_headers(
        base_headers=server.defaultHeaders,
        header_mapping=tool.paramMapping.headers,
        args=args,
        auth=server.auth.type,
        auth_key=server.auth.key,
        auth_value=server.auth.value,
    )
    query = _build_query(
        query_mapping=tool.paramMapping.query,
        args=args,
        auth=server.auth.type,
        auth_key=server.auth.key,
        auth_value=server.auth.value,
    )
    json_body, raw_body = _build_body(tool.paramMapping.body, tool.paramMapping.rawBody, args)

    method = tool.method
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(
            method.value,
            url,
            params=query or None,
            headers=headers or None,
            json=json_body if raw_body is None else None,
            content=raw_body,
        )

    content_type = resp.headers.get("content-type", "")
    response_text: Optional[str] = None
    response_json: Optional[Any] = None
    try:
        if "application/json" in content_type:
            response_json = resp.json()
        else:
            response_text = resp.text
    except Exception:
        response_text = resp.text

    # Optional pick using jsonpath-ng
    picked: Any = response_json if response_json is not None else response_text
    if tool.responseMapping and tool.responseMapping.pick and response_json is not None:
        try:
            from jsonpath_ng import parse as jp_parse  # type: ignore

            expr = jp_parse(tool.responseMapping.pick)
            matches = [m.value for m in expr.find(response_json)]
            if len(matches) == 1:
                picked = matches[0]
            else:
                picked = matches
        except Exception:
            # Fallback to full json if parsing fails
            picked = response_json

    return {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "url": str(resp.request.url) if resp.request else url,
        "data": picked,
    }


