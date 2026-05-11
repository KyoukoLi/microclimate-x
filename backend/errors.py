"""
Centralised error contract.

Every non-2xx response from the API has the same JSON shape so a
client (Vue SPA, curl, Postman, future mobile app) can rely on it.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error:      str          # short, stable identifier (snake_case)
    detail:     str          # human readable
    request_id: str | None = None
    context:    dict[str, Any] | None = None


# Canonical error identifiers — used as the `error` field. Adding new ones
# requires updating the OpenAPI docstring on the predict() endpoint too.
ERR_UPSTREAM_FAILURE = "upstream_failure"
ERR_INVALID_INPUT    = "invalid_input"
ERR_MODEL_ERROR      = "model_error"
ERR_INTERNAL         = "internal_error"
