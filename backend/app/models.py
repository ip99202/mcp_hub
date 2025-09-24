from __future__ import annotations

from enum import Enum
from typing import Dict, Optional, Any, Mapping

from pydantic import BaseModel, Field


class AuthType(str, Enum):
    """외부 API 인증 전달 방식"""
    bearer = "bearer"
    header = "header"
    query = "query"
    none = "none"


class AuthConfig(BaseModel):
    """서버 레벨의 인증 설정.

    - type: 인증 전달 방식
    - key/value: header/query 타입에서 사용할 키/값
    """
    type: AuthType = AuthType.none
    key: Optional[str] = None
    value: Optional[str] = None


class ServerConfig(BaseModel):
    """연결 대상 서버 설정."""
    name: str
    baseUrl: str
    auth: AuthConfig = Field(default_factory=AuthConfig)
    defaultHeaders: Dict[str, str] = Field(default_factory=dict)
    active: bool = True


class HttpMethod(str, Enum):
    """HTTP 메서드 열거형"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ParamMapping(BaseModel):
    """툴 인자와 HTTP 요청 요소 간의 매핑 정의.

    - path/query/headers/body: {요소키: 인자키}
    - rawBody: 인자키를 content로 그대로 전송할 때 사용
    """
    path: Dict[str, str] = Field(default_factory=dict)
    query: Dict[str, str] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Dict[str, str] = Field(default_factory=dict)
    rawBody: Optional[str] = None


class ResponseMapping(BaseModel):
    """응답 후처리 규칙."""
    pick: Optional[str] = None


class ToolBinding(BaseModel):
    """툴-HTTP 호출 바인딩 정의.

    - pathTemplate: /products/{id} 형태의 경로 템플릿
    - inputSchema: JSON Schema로 인자 검증에 사용
    - responseMapping: 응답에서 필요한 부분만 추출할 수 있음
    - active: 사용 여부 플래그
    """
    name: str
    description: Optional[str] = None
    method: HttpMethod
    pathTemplate: str
    paramMapping: ParamMapping = Field(default_factory=ParamMapping)
    inputSchema: Mapping[str, Any]
    responseMapping: Optional[ResponseMapping] = None
    active: bool = True


