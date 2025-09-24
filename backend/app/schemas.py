from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class CallRequest(BaseModel):
    """툴 호출 시 전달되는 인자 래퍼."""
    args: Dict[str, Any] = Field(default_factory=dict)


