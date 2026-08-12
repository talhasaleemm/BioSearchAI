from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.search_session import SearchSession
from app.models.user import User
from app.core.deps import get_current_user
from app.schemas.session import SessionCreateResponse

router = APIRouter()

@router.post("/", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new search session for the current user."""
    new_session = SearchSession(
        user_id=current_user.id,
        session_name="New Session"
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session
