from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/")
async def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve action history for the current user.

    Args:
        db: Database session.
        current_user: Injected authenticated user.

    Returns:
        Placeholder history response.
    """
    return {"message": "History endpoint placeholder"}
