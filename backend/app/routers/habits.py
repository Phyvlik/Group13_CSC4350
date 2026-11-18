"""Persisted habit selection and paginated verified observations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.feedback import HabitInput, HabitsOut, HistoryOut
from app.services.feedback import errors, habit_history, read_habits, select_habit

CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]

router = APIRouter(tags=["habits"])


@router.get("/habits", response_model=HabitsOut)
def get_habits(current_user: CurrentUser, db: Database):
    with errors(db):
        return read_habits(db, current_user.user_id)


@router.post("/habits", response_model=HabitsOut)
def post_habits(
    payload: HabitInput,
    current_user: CurrentUser,
    db: Database,
):
    with errors(db):
        result = select_habit(
            db, current_user.user_id, payload.metric_id, payload.active
        )
        db.commit()
        return result


@router.get("/habits/{metric_id}/history", response_model=HistoryOut)
def get_history(
    metric_id: UUID,
    current_user: CurrentUser,
    db: Database,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
):
    with errors(db):
        return habit_history(db, current_user.user_id, metric_id, limit, offset)
