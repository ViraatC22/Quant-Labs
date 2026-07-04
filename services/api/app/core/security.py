from typing import Annotated
from uuid import UUID

from fastapi import Header, HTTPException, status

DEMO_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id(x_user_id: Annotated[str | None, Header()] = None) -> UUID:
    """Temporary auth skeleton until real identity is added."""
    if not x_user_id:
        return DEMO_USER_ID

    try:
        return UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="x-user-id must be a valid UUID.",
        ) from exc
