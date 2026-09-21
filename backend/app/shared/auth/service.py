"""Signup / login / refresh / logout against `students` + auth_refresh_tokens."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.shared.db import get_engine
from app.shared.security import (
    REFRESH_TOKEN_EXPIRE_DAYS, create_access_token, hash_password,
    hash_refresh_token, new_refresh_token_plain, verify_password,
)


def _issue_tokens(engine, student_id: str, email: str) -> dict:
    access_token = create_access_token(student_id, email)
    refresh_plain = new_refresh_token_plain()
    refresh_hash = hash_refresh_token(refresh_plain)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO auth_refresh_tokens (student_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (student_id, refresh_hash, expires_at),
        )
    return {"access_token": access_token, "refresh_token": refresh_plain}


def signup(email: str, password: str, display_name: str) -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        existing = conn.exec_driver_sql(
            "SELECT student_id FROM students WHERE email = %s", (email,)
        ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    student_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO students (student_id, display_name, email, password_hash) VALUES (%s, %s, %s, %s)",
            (student_id, display_name, email, hash_password(password)),
        )
    tokens = _issue_tokens(engine, student_id, email)
    return {**tokens, "student": {"student_id": student_id, "email": email, "display_name": display_name}}


def login(email: str, password: str) -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT student_id, display_name, email, password_hash FROM students WHERE email = %s",
            (email,),
        ).mappings().fetchone()

    if not row or not row["password_hash"] or not verify_password(password, row["password_hash"]):
        # Same error either way — don't let login double as an email-enumeration oracle.
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    tokens = _issue_tokens(engine, row["student_id"], row["email"])
    return {**tokens, "student": {"student_id": row["student_id"], "email": row["email"], "display_name": row["display_name"]}}


def refresh(refresh_token: str) -> dict:
    engine = get_engine()
    token_hash = hash_refresh_token(refresh_token)
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            """
            SELECT rt.student_id, s.email, s.display_name, rt.expires_at, rt.revoked_at
            FROM auth_refresh_tokens rt JOIN students s ON s.student_id = rt.student_id
            WHERE rt.token_hash = %s
            """,
            (token_hash,),
        ).mappings().fetchone()

    if not row or row["revoked_at"] is not None or row["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired. Please log in again.")

    with engine.begin() as conn:  # rotate: revoke the used token so it can't be replayed
        conn.exec_driver_sql("UPDATE auth_refresh_tokens SET revoked_at = now() WHERE token_hash = %s", (token_hash,))
    tokens = _issue_tokens(engine, row["student_id"], row["email"])
    return {**tokens, "student": {"student_id": row["student_id"], "email": row["email"], "display_name": row["display_name"]}}


def logout(refresh_token: str) -> None:
    engine = get_engine()
    token_hash = hash_refresh_token(refresh_token)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "UPDATE auth_refresh_tokens SET revoked_at = now() WHERE token_hash = %s AND revoked_at IS NULL",
            (token_hash,),
        )