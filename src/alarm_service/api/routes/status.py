"""Service liveness endpoint."""

from fastapi import APIRouter

from alarm_service.api.schemas.status import StatusResponse

router = APIRouter(tags=["Status"])


@router.get("/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    """Confirm that the API is running; database readiness is added later."""
    return StatusResponse()
