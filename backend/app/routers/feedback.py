"""User-owned, explicit feedback computation and historical reads."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.feedback import FeedbackOut
from app.services.feedback import errors, read_feedback, recompute_feedback

CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]

router = APIRouter(tags=["feedback"])


@router.get("/sessions/{session_id}/feedback", response_model=FeedbackOut)
def get_feedback(
    session_id: UUID,
    current_user: CurrentUser,
    db: Database,
):
    with errors(db):
        return read_feedback(db, current_user.user_id, session_id)


@router.post("/sessions/{session_id}/feedback/recompute", response_model=FeedbackOut)
def post_feedback(
    session_id: UUID,
    current_user: CurrentUser,
    db: Database,
):
    with errors(db):
        result = recompute_feedback(db, current_user.user_id, session_id)
        db.commit()
        return result
