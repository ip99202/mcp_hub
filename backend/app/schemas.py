from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class CallRequest(BaseModel):
    args: Dict[str, Any] = Field(default_factory=dict)


