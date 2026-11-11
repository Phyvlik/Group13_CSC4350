from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import create_access_token, get_current_user
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.enums import AccountStatus, UserRole
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UpdateMeRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(user=UserOut.from_user(user), access_token=create_access_token(user.user_id))


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    """Create a trader account and return it with an access token."""
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role=UserRole.TRADER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Another request registered the same email between the check and the insert.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
    db.refresh(user)
    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    """Exchange email and password for an access token."""
    user = db.scalar(select(User).where(User.email == body.email))
    if (
        user is None
        or not verify_password(body.password, user.password_hash)
        or user.account_status != AccountStatus.ACTIVE
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _auth_response(user)


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Return the signed in user."""
    return UserOut.from_user(current_user)


@router.patch("/me", response_model=UserOut)
def update_me(
    body: UpdateMeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """Update the signed in user's display name and/or password."""
    if body.password is not None:
        if not verify_password(body.current_password or "", current_user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        current_user.password_hash = hash_password(body.password)
    if body.display_name is not None:
        current_user.display_name = body.display_name

    db.commit()
    db.refresh(current_user)
    return UserOut.from_user(current_user)
