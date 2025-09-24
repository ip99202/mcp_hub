from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

import httpx
from pydantic import ValidationError

from .models import ServerConfig, ToolBinding, AuthType, HttpMethod


class BindingError(Exception):
    pass


def _interpolate_path(path_template: str, path_mapping: Dict[str, str], args: Dict[str, Any]) -> str:
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
    query: Dict[str, Any] = {}
    for q_name, arg_key in query_mapping.items():
        if arg_key in args and args[arg_key] is not None:
            query[q_name] = args[arg_key]
    if auth == AuthType.query and auth_key and auth_value:
        query.setdefault(auth_key, auth_value)
    return query


def _build_body(body_mapping: Dict[str, str], raw_body_key: Optional[str], args: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
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


