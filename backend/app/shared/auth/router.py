from fastapi import APIRouter, Depends

from app.shared import db
from app.shared.auth import service
from app.shared.auth.dependencies import get_current_student
from app.shared.auth.schemas import (
    LoginRequest, LogoutRequest, RefreshRequest, SignupRequest, StudentOut, TokenResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(payload: SignupRequest):
    return service.signup(payload.email, payload.password, payload.display_name)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    return service.login(payload.email, payload.password)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest):
    return service.refresh(payload.refresh_token)


@router.post("/logout", status_code=204)
def logout(payload: LogoutRequest):
    service.logout(payload.refresh_token)


@router.get("/me", response_model=StudentOut)
def me(student=Depends(get_current_student)):
    engine = db.get_engine()
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT student_id, email, display_name FROM students WHERE student_id = %s",
            (student["student_id"],),
        ).mappings().fetchone()
    return dict(row)