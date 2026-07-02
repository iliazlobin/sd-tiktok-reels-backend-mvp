import json
from base64 import b64decode, b64encode
from datetime import datetime
from uuid import UUID as UUID_TYPE

from pydantic import BaseModel, Field


class CursorToken(BaseModel):
    """Cursor pagination token — opaque to clients, encoded as base64 JSON."""

    score: float | None = None
    created_at: str | None = None
    id: str = Field(..., description="UUID of the last item")


def encode_cursor(score: float | None, item_id: UUID_TYPE) -> str:
    """Encode a cursor token as base64 JSON."""
    payload: dict[str, str | float] = {"id": str(item_id)}
    if score is not None:
        payload["score"] = float(score)
    return b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def encode_cursor_datetime(created_at: datetime, item_id: UUID_TYPE) -> str:
    """Encode a cursor token sourced from a timestamp + UUID."""
    payload = {"created_at": created_at.isoformat(), "id": str(item_id)}
    return b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decode_cursor(token: str) -> dict:
    """Decode a cursor token. Raises ValueError if malformed."""
    try:
        decoded = json.loads(b64decode(token.encode()).decode())
        if "id" not in decoded:
            raise ValueError("cursor missing 'id'")
        return decoded
    except (json.JSONDecodeError, Exception) as exc:
        raise ValueError(f"malformed cursor: {exc}") from exc


class PaginatedResponse(BaseModel):
    """Generic paginated response with next_cursor."""

    next_cursor: str | None = Field(default=None, description="Opaque cursor for the next page")
