"""Response contract for the service status endpoint."""

from typing import Literal

from pydantic import BaseModel


class StatusResponse(BaseModel):
    status: Literal["ok"] = "ok"
