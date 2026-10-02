"""Service liveness endpoint."""

from fastapi import APIRouter

from alarm_service.api.schemas.status import StatusResponse

router = APIRouter(tags=["Status"])


@router.get("/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    """Confirm HTTP liveness without querying the database."""
    return StatusResponse()
