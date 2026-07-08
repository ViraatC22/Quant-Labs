from typing import Annotated
from uuid import UUID

from fastapi import Header, HTTPException, status

from app.core.config import settings

DEMO_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id(x_user_id: Annotated[str | None, Header()] = None) -> UUID:
    """Temporary identity skeleton until real auth is added.

    The x-user-id header carries no authentication, so it is only honored in
    local dev (``TRUST_USER_HEADER``). Any non-local deployment binds every
    request to the demo user and ignores the header, so a hosted instance can
    never let a caller impersonate another user by setting one.
    """
    if not settings.trust_user_header or not x_user_id:
        return DEMO_USER_ID

    try:
        return UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="x-user-id must be a valid UUID.",
        ) from exc
