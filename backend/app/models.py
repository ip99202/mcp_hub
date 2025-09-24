from __future__ import annotations

from enum import Enum
from typing import Dict, Optional, Any, Mapping

from pydantic import BaseModel, Field


class AuthType(str, Enum):
    bearer = "bearer"
    header = "header"
    query = "query"
    none = "none"


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
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ParamMapping(BaseModel):
    path: Dict[str, str] = Field(default_factory=dict)
    query: Dict[str, str] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Dict[str, str] = Field(default_factory=dict)
    rawBody: Optional[str] = None


class ResponseMapping(BaseModel):
    pick: Optional[str] = None


class ToolBinding(BaseModel):
    name: str
    description: Optional[str] = None
    method: HttpMethod
    pathTemplate: str
    paramMapping: ParamMapping = Field(default_factory=ParamMapping)
    inputSchema: Mapping[str, Any]
    responseMapping: Optional[ResponseMapping] = None
    active: bool = True


